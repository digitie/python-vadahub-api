"""GDAL native 객체를 한 worker 안에서만 사용하는 bounded SHP reader."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import closing
from datetime import date
import codecs
from pathlib import Path
import re
import threading
from types import MappingProxyType
from typing import Any
import zipfile

from ._archive import ArchiveLimits, inspect_archive
from .exceptions import SchemaError, SpatialDependencyError, UnknownCrsError
from .models import ArchiveReceipt, DatasetLayer, SpatialFeature


def _native() -> tuple[Any, Any, Any]:
    try:
        from osgeo import gdal, ogr, osr  # type: ignore[import-not-found,import-untyped]
    except ImportError:
        raise SpatialDependencyError('공간 로드는 시스템 GDAL과 같은 버전의 osgeo binding이 필요합니다. docs/gdal.md 참조') from None
    if int(gdal.VersionInfo()) < 3080000:
        raise SpatialDependencyError('GDAL 3.8 이상 binding이 필요합니다')
    return gdal, ogr, osr


def _field_mapping(text: str, fields: set[str]) -> dict[str, str]:
    pairs = re.findall(r'inFieldName=(c[0-9]+), columnName=([^,}]+)', text)
    mapping = dict(pairs)
    if len(mapping) != len(pairs) or set(mapping) != fields or len(set(mapping.values())) != len(mapping):
        raise SchemaError('TXT 필드 매핑의 누락·중복·DBF 불일치')
    if any(not value.strip() or value != value.strip() for value in mapping.values()):
        raise SchemaError('잘못된 TXT columnName')
    return mapping


def _value(name: str, value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip() or None
    if value is not None and (name.endswith('_ymd') or name in ('symd', 'eymd', 'cycle_symd', 'cycle_eymd')):
        if not isinstance(value, str) or not re.fullmatch('[0-9]{8}', value):
            raise SchemaError('잘못된 원천 일자 값')
        try:
            return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        except ValueError:
            raise SchemaError('유효하지 않은 원천 일자') from None
    return value


def _iter_sync(path: Path, layer: DatasetLayer, limits: ArchiveLimits, source_crs: str | None,
               encoding: str | None, max_features: int, receipt: ArchiveReceipt | None,
               stop: threading.Event) -> Generator[SpatialFeature, None, None]:
    checksum, _members = inspect_archive(path, limits, layer.table_name)
    if receipt is not None and (receipt.sha256 != checksum or receipt.layer != layer):
        raise SchemaError('원문과 receipt의 해시/자료 식별이 다릅니다')
    gdal, ogr, osr = _native()
    with zipfile.ZipFile(path) as archive:
        name = layer.table_name
        has_prj = name + '.prj' in archive.namelist()
        if archive.getinfo(name + '.txt').file_size > 8 * 1024 * 1024:
            raise SchemaError('TXT 매핑 8MiB 상한 초과')
        raw_text = archive.read(name + '.txt')
        try:
            text = raw_text.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = raw_text.decode('cp949')
            except UnicodeDecodeError:
                raise SchemaError('TXT 매핑 인코딩 오류') from None
        selected_encoding = encoding
        if selected_encoding is None and name + '.cpg' in archive.namelist():
            try:
                selected_encoding = archive.read(name + '.cpg').decode('ascii').strip()
            except UnicodeDecodeError:
                raise SchemaError('CPG 인코딩 이름 오류') from None
            if selected_encoding == '949':
                selected_encoding = 'cp949'
        selected_encoding = selected_encoding or 'cp949'
        try:
            codecs.lookup(selected_encoding)
        except LookupError:
            raise SchemaError('지원하지 않는 DBF 인코딩') from None
    try:
        with gdal.ExceptionMgr(), ogr.ExceptionMgr(), osr.ExceptionMgr(), gdal.quiet_errors(), \
                gdal.config_options({'SHAPE_ENCODING': selected_encoding}, thread_local=True):
            # driver와 VFS는 검증한 로컬 ZIP/SHP로 제한한다.
            with gdal.OpenEx('/vsizip/' + path.resolve().as_posix() + '/' + name + '.shp', gdal.OF_VECTOR,
                             allowed_drivers=['ESRI Shapefile'], open_options=['ENCODING=' + selected_encoding]) as dataset:
                native_layer = dataset.GetLayer(0)
                definition = native_layer.GetLayerDefn()
                fields = {definition.GetFieldDefn(i).GetName() for i in range(definition.GetFieldCount())}
                mapping = _field_mapping(text, fields)
                expected = native_layer.GetFeatureCount()
                if expected < 0 or expected > max_features:
                    raise SchemaError('SHP 레코드 수량 상한/미확정')
                reference = native_layer.GetSpatialRef()
                if has_prj and reference is None:
                    raise UnknownCrsError('.prj가 있으나 GDAL이 CRS를 읽지 못했습니다')
                reference = reference.Clone() if reference is not None else None
                evidence = 'archive_prj' if reference is not None else None
                if source_crs is not None:
                    if not re.fullmatch('EPSG:[0-9]+', source_crs) and not source_crs.startswith(('GEOGCS[','PROJCS[','GEOGCRS[','PROJCRS[','COMPOUNDCRS[')):
                        raise UnknownCrsError('CRS는 EPSG 코드 또는 WKT여야 합니다')
                    supplied = osr.SpatialReference()
                    try:
                        supplied.SetFromUserInput(source_crs)
                    except RuntimeError:
                        raise UnknownCrsError('호출자 CRS를 해석하지 못했습니다') from None
                    if reference is not None and not reference.IsSame(supplied):
                        raise UnknownCrsError('SHP .prj와 호출자 CRS가 충돌합니다')
                    reference = supplied
                    evidence = 'caller:' + source_crs
                transform = None
                wkt = None
                if reference is not None:
                    reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                    wkt = reference.ExportToWkt()
                    target = osr.SpatialReference()
                    target.ImportFromEPSG(4326)
                    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                    transform = osr.CoordinateTransformation(reference, target)
                seen: set[str] = set()
                actual = 0
                while True:
                    if stop.is_set():
                        return
                    gdal.ErrorReset()
                    feature = native_layer.GetNextFeature()
                    if feature is None:
                        if gdal.GetLastErrorType() >= gdal.CE_Warning:
                            raise SchemaError('GDAL 반복 종료 오류')
                        break
                    raw = feature.items()
                    attrs = {mapping[key]: _value(mapping[key], value) for key, value in raw.items()}
                    id_field = 'gid' if attrs.get('gid') is not None else 'ogr_fid'
                    record_id = str(attrs['gid'] if id_field == 'gid' else feature.GetFID())
                    if record_id in seen:
                        raise SchemaError('SHP 레코드 식별자 중복')
                    seen.add(record_id)
                    geometry = feature.GetGeometryRef()
                    raw_wkb = wgs84 = geometry_type = None
                    if geometry is not None and not geometry.IsEmpty():
                        if geometry.WkbSize() > 16 * 1024 * 1024 or not geometry.IsValid():
                            raise SchemaError('geometry 크기 상한 또는 유효성 오류')
                        raw_wkb = bytes(geometry.ExportToWkb())
                        geometry_type = geometry.GetGeometryName()
                        if transform is not None:
                            converted = geometry.Clone()
                            if converted.Transform(transform) != 0 or not converted.IsValid():
                                raise UnknownCrsError('WGS84 좌표변환 실패')
                            wgs84 = bytes(converted.ExportToWkb())
                    if gdal.GetLastErrorType() >= gdal.CE_Warning:
                        raise SchemaError('GDAL 디코딩/공간 처리 경고')
                    actual += 1
                    yield SpatialFeature(layer, record_id, id_field, MappingProxyType(raw), MappingProxyType(attrs),
                                         raw_wkb, geometry_type, wkt, evidence, wgs84, checksum,
                                         receipt.collected_at if receipt else None)
                if actual != expected:
                    raise SchemaError('SHP 선언 수량과 실제 반복 수량이 다릅니다')
    except RuntimeError:
        raise SchemaError('GDAL이 SHP/CRS를 읽지 못했습니다') from None


async def iter_file(path: str | Path, *, layer: DatasetLayer, source_crs: str | None = None,
                    encoding: str | None = None, batch_size: int = 64, max_features: int = 1000000,
                    limits: ArchiveLimits = ArchiveLimits(), receipt: ArchiveReceipt | None = None) -> AsyncGenerator[SpatialFeature, None]:
    """전용 worker에서만 GDAL 객체를 사용하고 최대 2 batch를 대기시킨다."""
    if (isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 1024
            or isinstance(max_features, bool) or not isinstance(max_features, int) or not 1 <= max_features <= 10000000):
        raise ValueError('batch_size 1..1024, max_features 1..10000000 정수가 필요합니다')
    # 잘못된 모델이 GDAL 경로를 구성하지 않게 테이블 ID도 검증한다.
    if not re.fullmatch('[a-zA-Z][a-zA-Z0-9_]*', layer.table_name):
        raise SchemaError('안전하지 않은 layer 이름입니다')
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[list[SpatialFeature] | Exception | None] = asyncio.Queue(maxsize=2)
    stop = threading.Event()

    def send(value: list[SpatialFeature] | Exception | None) -> bool:
        if stop.is_set():
            return False
        future = asyncio.run_coroutine_threadsafe(queue.put(value), loop)
        while not stop.is_set():
            try:
                future.result(timeout=0.1)
                return True
            except FutureTimeout:
                continue
        future.cancel()
        return False

    def worker() -> None:
        try:
            batch: list[SpatialFeature] = []
            batch_bytes = 0
            with closing(_iter_sync(Path(path), layer, limits, source_crs, encoding, max_features, receipt, stop)) as records:
                for feature in records:
                    estimate = (len(feature.geometry_wkb or b'') + len(feature.wgs84_wkb or b'')
                                + sum(len(str(value).encode('utf-8')) * 2 for value in feature.raw_attributes.values()) + 512)
                    if batch and batch_bytes + estimate > 4 * 1024 * 1024:
                        if not send(batch):
                            return
                        batch, batch_bytes = [], 0
                    batch.append(feature)
                    batch_bytes += estimate
                    if len(batch) == batch_size or batch_bytes >= 4 * 1024 * 1024:
                        if not send(batch):
                            return
                        batch, batch_bytes = [], 0
            if batch and not send(batch):
                return
        except Exception as exc:
            send(exc)
        finally:
            send(None)

    task = asyncio.create_task(asyncio.to_thread(worker))
    try:
        while True:
            value = await queue.get()
            if value is None:
                break
            if isinstance(value, Exception):
                raise value
            for item in value:
                yield item
    finally:
        stop.set()
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        task.result()
