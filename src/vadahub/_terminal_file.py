"""공식 터미널 CSV의 제한된 디코딩과 단일 worker OGR WKT 읽기."""
from collections.abc import AsyncGenerator, Iterator, Generator
from contextlib import aclosing
from datetime import date, datetime
import csv
import hashlib
import io
import math
from pathlib import Path
import re
import threading
from types import MappingProxyType

from .exceptions import ArchiveError, SchemaError
from .models import PassengerTerminal, TerminalFileReceipt
from .parse import _native
from ._stream import iter_worker

MAX_BYTES = 16 * 1024 * 1024
SOURCE_URL = 'https://www.data.go.kr/data/15148558/fileData.do'
COLUMNS = ('공간정보일련번호', '최소엑스좌표', '최소와이좌표', '최대엑스좌표', '최대와이좌표',
    '종착지명', '시설도로명주소', '엑스좌표', '와이좌표', '여객터미널조사년도', '조사기관명', '공간정보')


def _read(path: Path) -> tuple[bytes, str]:
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ArchiveError('터미널 CSV16MiB 상한 초과')
    return data, hashlib.sha256(data).hexdigest()


def _rows(data: bytes, max_features: int) -> Iterator[dict[str, str]]:
    try:
        text = data.decode('cp949', errors='strict')
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        if tuple(next(reader, ())) != COLUMNS:
            raise SchemaError('공식 터미널 CSV 헤더가 바뀌었습니다')
        seen = set()
        for number, cells in enumerate(reader, 1):
            if number > max_features:
                raise SchemaError('터미널 CSV 행수 상한 초과')
            if len(cells) != len(COLUMNS):
                raise SchemaError('터미널 CSV 열수 불일치')
            row = dict(zip(COLUMNS, cells, strict=True))
            record_id = row['공간정보일련번호']
            if not re.fullmatch(r'[0-9]{1,20}', record_id) or record_id in seen:
                raise SchemaError('터미널 CSV ID 형식/중복 오류')
            seen.add(record_id)
            year = row['여객터미널조사년도'].strip()
            if year and (not re.fullmatch(r'[0-9]{4}', year) or int(year) == 0):
                raise SchemaError('터미널 CSV 조사년도 오류')
            yield row
    except (UnicodeError, csv.Error) as exc:
        raise SchemaError('터미널 CSV CP949/형식 오류') from exc


def inspect_terminal(path: Path) -> tuple[str, int]:
    """다운로드 검사는 GDAL을 요구하지 않는다. 원문 bytes와 구조를 대조한다."""
    data, checksum = _read(path)
    count = sum(1 for _ in _rows(data, 10000))
    if count == 0:
        raise SchemaError('터미널 CSV가 비어 있습니다')
    return checksum, len(data)


def _records(path: Path, max_features: int, receipt: TerminalFileReceipt | None,
             stop: threading.Event) -> Generator[PassengerTerminal, None, None]:
    data, checksum = _read(path)
    if receipt is not None and (not isinstance(receipt, TerminalFileReceipt)
            or receipt.schema_version != '1'
            or receipt.source != 'data.go.kr:15148558' or receipt.source_url != SOURCE_URL
            or receipt.content_date != date(2014, 12, 31) or receipt.sha256 != checksum
            or receipt.byte_size != len(data) or not isinstance(receipt.collected_at, datetime)
            or receipt.collected_at.tzinfo is None
            or receipt.collected_at.utcoffset() is None):
        raise SchemaError('터미널 원문과 receipt의 출처/버전/해시/시점 불일치')
    gdal, ogr, _osr = _native()
    with gdal.ExceptionMgr(), ogr.ExceptionMgr(), gdal.quiet_errors():
        for row in _rows(data, max_features):
            if stop.is_set(): return
            geometry = None
            try:
                text = row['공간정보'].strip()
                wkb = None
                valid = None
                if text:
                    gdal.ErrorReset()
                    try:
                        geometry = ogr.CreateGeometryFromWkt(text)
                        if geometry is None or geometry.GetGeometryType() != ogr.wkbPoint:
                            raise SchemaError('터미널 공간정보는 POINT WKT여야 합니다')
                        if not geometry.IsEmpty():
                            if not all(math.isfinite(value) for value in (geometry.GetX(), geometry.GetY())):
                                raise SchemaError('터미널 WKT 좌표가 유한수가 아닙니다')
                            valid = bool(geometry.IsValid())
                            if not valid: raise SchemaError('터미널 WKT geometry 유효성 오류')
                            wkb = bytes(geometry.ExportToWkb())
                        if gdal.GetLastErrorType() != 0:
                            raise SchemaError('터미널 WKT 읽기 경고/오류')
                    except RuntimeError as exc:
                        raise SchemaError('터미널 WKT 읽기 오류') from exc
            finally:
                geometry = None
            year = row['여객터미널조사년도'].strip()
            yield PassengerTerminal(receipt.source if receipt else 'local_csv:' + checksum,
                row['공간정보일련번호'], row['종착지명'].strip() or None, row['시설도로명주소'].strip() or None,
                int(year) if year else None, MappingProxyType(row), wkb, valid, checksum,
                receipt.source_url if receipt else None, receipt.collected_at if receipt else None)


async def iter_terminal_file(path: str | Path, *, receipt: TerminalFileReceipt | None = None,
        batch_size: int = 64, max_features: int = 10000) -> AsyncGenerator[PassengerTerminal, None]:
    """원문16MiB·행10000 제한. 공식 receipt가 없으면 local_csv 출처로 둔다."""
    if (isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 256
            or isinstance(max_features, bool) or not isinstance(max_features, int) or not 1 <= max_features <= 10000):
        raise ValueError('batch_size1..256, max_features1..10000 정수가 필요합니다')
    def producer(stop: threading.Event) -> Generator[PassengerTerminal, None, None]:
        return _records(Path(path), max_features, receipt, stop)
    def estimate(item: PassengerTerminal) -> int:
        return sum(len(s.encode('utf-8')) * 2 for s in item.raw_attributes.values()) + len(item.geometry_wkb or b'') + 512
    async with aclosing(iter_worker(producer, batch_size=batch_size, estimate=estimate)) as stream:
        async for row in stream: yield row
