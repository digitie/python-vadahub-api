"""검증한 원문의 immutable 버전·원자 manifest와 고아 복구."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any
import uuid

from filelock import FileLock

from ._archive import ArchiveLimits, inspect_archive
from ._catalog import identifier, history
from ._io import run_io
from .exceptions import ArchiveError, SchemaError
from .models import ArchiveReceipt, DatasetLayer, Dataset, LibraryResource, LibraryArchiveReceipt


@dataclass(frozen=True, slots=True)
class StoredArchive:
    """원문 경로와 payload 지문. ZIP timestamp 차이와 내용 변경을 구분한다."""
    receipt: ArchiveReceipt | LibraryArchiveReceipt
    content_fingerprint: str
    object_key: str


def _key(layer: DatasetLayer | LibraryResource) -> str:
    if isinstance(layer,LibraryResource):
        dataset = layer.dataset
        if dataset.catalog not in ('documents','statistics'):
            raise ArchiveError('자료실 ZIP 보관은 문서/통계만 지원합니다')
        return '/'.join(('library',dataset.catalog,identifier(dataset.dataset_id),history(dataset.history_date),identifier(layer.resource_id)))
    if not isinstance(layer.table_name, str) or not re.fullmatch('[a-zA-Z][a-zA-Z0-9_]*', layer.table_name):
        raise ArchiveError('잘못된 원문 table 식별자')
    return '/'.join((identifier(layer.dataset_id), history(layer.history_date), identifier(layer.layer_id), layer.table_name))


def _sha(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ArchiveError('잘못된 SHA256')
    return value


def _fingerprint(members: tuple[tuple[str, str], ...]) -> str:
    return hashlib.sha256(json.dumps(sorted(members),separators=(',', ':'),ensure_ascii=True).encode()).hexdigest()


def _receipt_key(receipt: ArchiveReceipt | LibraryArchiveReceipt) -> str:
    return _key(receipt.layer if isinstance(receipt,ArchiveReceipt) else receipt.resource)


def _serialize(receipt: ArchiveReceipt | LibraryArchiveReceipt) -> dict:
    item = asdict(receipt)
    item['collected_at'] = receipt.collected_at.isoformat()
    item.pop('local_path')
    return item


def _json(path: Path, cap: int) -> Any:
    try:
        if path.stat().st_size > cap:
            raise ArchiveError('보관 metadata 크기 상한 초과')
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError, OSError):
        raise ArchiveError('보관 metadata 누락/읽기/JSON 오류') from None


def _atomic_json(path: Path, value: Any) -> None:
    data = json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')
    if len(data) > 8 * 1024 * 1024:
        raise ArchiveError('manifest 8MiB 상한 초과')
    descriptor, name = tempfile.mkstemp(prefix='.manifest-',suffix='.part',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)


class LocalArchiveStore:
    """로컬 OS의 cross-process lock을 쓰는 원문 저장소. 기본 삭제 없음.

    commit worker가 시작된 뒤 취소되면 commit이 완료될 수 있다. worker 종료까지 기다리고
    이전 원문/버전은 보존한다. 재실행 또는 recover로 완료 여부를 확인한다.
    같은 root의 Windows/WSL 혼합 writer·네트워크 FS 분산 lock은 지원하지 않는다.
    """
    def __init__(self, root: str | Path, *, limits: ArchiveLimits = ArchiveLimits(), lock_timeout: float = 5) -> None:
        if not isinstance(lock_timeout,(int,float)) or isinstance(lock_timeout,bool) or not math.isfinite(lock_timeout) or lock_timeout <= 0:
            raise ValueError('lock_timeout은 양의 유한 초여야 합니다')
        self.root = Path(root).absolute()
        self.limits = limits
        self.lock_timeout = lock_timeout

    def _lock(self) -> FileLock:
        self.root.mkdir(parents=True,exist_ok=True)
        return FileLock(str(self.root/'.store.lock'),timeout=self.lock_timeout)

    def _read_manifest(self) -> dict:
        path = self.root/'manifest.json'
        if not path.exists():
            return {'schema_version':'1','entries':{}}
        data = _json(path,8*1024*1024)
        if (not isinstance(data,dict) or data.get('schema_version') != '1'
                or not isinstance(data.get('entries'),dict) or len(data['entries']) > 10000):
            raise ArchiveError('manifest schema 오류')
        for key, values in data['entries'].items():
            if not isinstance(values,list) or not values or len(values) > 10000:
                raise ArchiveError('manifest 버전 목록 오류')
            seen = set()
            for item in values:
                stored = self._decode(item)
                if _receipt_key(stored.receipt) != key or stored.receipt.sha256 in seen:
                    raise ArchiveError('manifest 식별/중복 오류')
                seen.add(stored.receipt.sha256)
        return data

    def _decode(self, item: Any) -> StoredArchive:
        try:
            if not isinstance(item,dict) or item.get('schema_version') != '1':
                raise ArchiveError('receipt schema 오류')
            scope: DatasetLayer | LibraryResource
            if 'resource' in item:
                raw = dict(item['resource'])
                raw['dataset'] = Dataset(**raw['dataset'])
                raw['raw_availability'] = tuple(tuple(pair) for pair in raw.get('raw_availability',()))
                scope = LibraryResource(**raw)
            else:
                scope = DatasetLayer(**item['layer'])
            key, checksum = _key(scope), _sha(item['sha256'])
            collected = datetime.fromisoformat(item['collected_at'])
            if collected.tzinfo is None or collected.utcoffset() is None:
                raise ArchiveError('receipt 수집시점 timezone 누락')
            size = item['byte_size']
            if isinstance(size,bool) or not isinstance(size,int) or size <= 0:
                raise ArchiveError('receipt 크기 오류')
            members = tuple((name,_sha(value)) for name,value in item['member_sha256'])
            object_key = 'objects/' + key + '/' + checksum
            receipt: ArchiveReceipt | LibraryArchiveReceipt
            if isinstance(scope,LibraryResource):
                receipt = LibraryArchiveReceipt(scope,item['source_url'],collected,checksum,size,
                                                self.root/object_key/'archive.zip',members)
            else:
                receipt = ArchiveReceipt(scope,item['source_url'],collected,checksum,size,
                                         self.root/object_key/'archive.zip',members)
            return StoredArchive(receipt,_fingerprint(members),object_key)
        except (KeyError,TypeError,ValueError,SchemaError):
            raise ArchiveError('receipt 필드 형식 오류') from None

    def _verify(self, stored: StoredArchive, *, sidecar: bool = False) -> None:
        receipt = stored.receipt
        if sidecar and self._decode(_json(receipt.local_path.parent/'receipt.json',1024*1024)) != stored:
            raise ArchiveError('manifest와 object receipt 불일치')
        try:
            checksum,members = inspect_archive(receipt.local_path,self.limits,
                                                receipt.layer.table_name if isinstance(receipt,ArchiveReceipt) else None,
                                                allow_directories=isinstance(receipt,LibraryArchiveReceipt))
        except OSError:
            raise ArchiveError('보관 원문 누락/읽기 오류') from None
        if (checksum != receipt.sha256 or members != receipt.member_sha256
                or receipt.local_path.stat().st_size != receipt.byte_size):
            raise ArchiveError('보관 원문/receipt 해시·멤버·크기 불일치')

    def _prepare(self, stage: Path, receipt: ArchiveReceipt | LibraryArchiveReceipt) -> None:
        self._decode(_serialize(receipt))
        stage.mkdir(parents=True,exist_ok=False)
        if receipt.local_path.stat().st_size > self.limits.archive_bytes:
            raise ArchiveError('원문 보관 크기 상한 초과')
        copied = 0
        with receipt.local_path.open('rb') as source, (stage/'archive.zip').open('xb') as output:
            while block := source.read(1024*1024):
                copied += len(block)
                if copied > min(receipt.byte_size,self.limits.archive_bytes):
                    raise ArchiveError('복사 중 원문 크기가 receipt/상한을 초과했습니다')
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        candidate = replace(receipt,local_path=stage/'archive.zip')
        self._verify(StoredArchive(candidate,_fingerprint(candidate.member_sha256),''))
        _atomic_json(stage/'receipt.json',_serialize(candidate))

    def _commit(self, stage: Path) -> StoredArchive:
        with self._lock():
            manifest = self._read_manifest()
            item = _json(stage/'receipt.json',1024*1024)
            stored = self._decode(item)
            target = stored.receipt.local_path.parent
            if target.exists():
                existing = self._decode(_json(target/'receipt.json',1024*1024))
                if existing.object_key != stored.object_key:
                    raise ArchiveError('기존 원문 receipt 식별 불일치')
                self._verify(existing,sidecar=True)
                stored, item = existing, _serialize(existing.receipt)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                os.rename(stage,target)
            values = manifest['entries'].setdefault(_receipt_key(stored.receipt),[])
            if not any(entry['sha256'] == stored.receipt.sha256 for entry in values):
                values.append(item)
                _atomic_json(self.root/'manifest.json',manifest)
            return stored

    async def put(self, receipt: ArchiveReceipt | LibraryArchiveReceipt) -> StoredArchive:
        """원문을 다시 검증해 보관한다. 같은 scope+SHA면 기존 버전·수집시점을 반환한다."""
        stage = self.root/'.staging'/uuid.uuid4().hex
        try:
            await run_io(self._prepare,stage,receipt)
            return await run_io(self._commit,stage)
        finally:
            await run_io(shutil.rmtree,stage,True)

    def _versions(self, layer: DatasetLayer | LibraryResource) -> tuple[StoredArchive, ...]:
        with self._lock():
            data = self._read_manifest()
            values = tuple(self._decode(item) for item in data['entries'].get(_key(layer),[]))
            for stored in values:
                self._verify(stored,sidecar=True)
            return values

    async def versions(self, layer: DatasetLayer | LibraryResource) -> tuple[StoredArchive, ...]:
        """삽입 순서의 버전을 해시 검증 후 반환한다. 자동 최신 시점 추정 없음."""
        return await run_io(self._versions,layer)

    def _recover(self) -> tuple[StoredArchive, ...]:
        with self._lock():
            manifest = self._read_manifest()
            for values in manifest['entries'].values():
                for item in values:
                    self._verify(self._decode(item),sidecar=True)
            recovered = []
            count = 0
            for path in (self.root/'objects').rglob('receipt.json'):
                count += 1
                if count > 10000:
                    raise ArchiveError('고아 검사 10000개 상한 초과')
                item = _json(path,1024*1024)
                stored = self._decode(item)
                if stored.receipt.local_path.parent != path.parent:
                    raise ArchiveError('고아 receipt 경로/식별 불일치')
                self._verify(stored,sidecar=True)
                values = manifest['entries'].setdefault(_receipt_key(stored.receipt),[])
                if not any(entry['sha256'] == stored.receipt.sha256 for entry in values):
                    values.append(item)
                    recovered.append(stored)
            if recovered:
                _atomic_json(self.root/'manifest.json',manifest)
            return tuple(recovered)

    async def recover(self) -> tuple[StoredArchive, ...]:
        """manifest 미기록 object를 재검증 후 원자 복구한다. 손상은 오류이며 삭제하지 않는다."""
        return await run_io(self._recover)
