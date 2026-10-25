"""원문을 보존하는 공식 선착장 CSV의 제한 읽기."""
from collections.abc import AsyncGenerator, Generator, Iterator
from contextlib import aclosing
from datetime import date, datetime
import csv
import hashlib
import io
from pathlib import Path
import threading
from types import MappingProxyType

from ._stream import iter_worker
from ._terminal_source import _attachment
from .exceptions import AccessDeniedError, ArchiveError, SchemaError
from .models import OfficialPier, PierFileReceipt

SOURCE_URL = 'https://www.data.go.kr/data/15070386/fileData.do'
SOURCE = 'data.go.kr:15070386'
CONTENT_DATE = date(2020, 10, 20)
NAME = '해양경찰청_선착장 정보_10/20/2020'
FILENAME = NAME.replace('/', '_') + '.csv'
MAX_BYTES = 16 * 1024 * 1024
COLUMNS = ('선착장명', '위도도', '위도분', '위도초', '경도도', '경도분', '경도초', '주정박지유무',
    '유선기착지유무', '도선기착지유무', '도서지역유무', '도서지역명', '출장소유무', '서센터유무', '선착장주소')


def attachment(url: str, *, final: bool = False) -> tuple[str, str]:
    return _attachment(url, final=final, name=NAME)


def _read(path: Path) -> tuple[bytes, str]:
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ArchiveError('선착장 CSV16MiB 상한 초과')
    return data, hashlib.sha256(data).hexdigest()


def _rows(data: bytes, max_features: int) -> Iterator[dict[str, str]]:
    try:
        reader = csv.reader(io.StringIO(data.decode('cp949', errors='strict'), newline=''), strict=True)
        if tuple(next(reader, ())) != COLUMNS:
            raise SchemaError('공식 선착장 CSV15필드 헤더가 바뀌었습니다')
        for number, cells in enumerate(reader, 1):
            if number > max_features or len(cells) != len(COLUMNS):
                raise SchemaError('선착장 CSV 행수 상한/열수 불일치')
            yield dict(zip(COLUMNS, cells, strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise SchemaError('선착장 CSV CP949/형식 오류') from exc


def inspect_pier(path: Path) -> tuple[str, int]:
    data, checksum = _read(path)
    if sum(1 for _ in _rows(data, 10000)) == 0:
        raise SchemaError('선착장 CSV가 비어 있습니다')
    return checksum, len(data)


def _records(path: Path, max_features: int, receipt: PierFileReceipt | None,
             stop: threading.Event) -> Generator[OfficialPier, None, None]:
    data, checksum = _read(path)
    if receipt is not None:
        if (not isinstance(receipt, PierFileReceipt) or receipt.schema_version != '1'
                or receipt.source != SOURCE or receipt.source_url != SOURCE_URL
                or receipt.content_date != CONTENT_DATE or receipt.sha256 != checksum
                or type(receipt.byte_size) is not int or receipt.byte_size != len(data)
                or not isinstance(receipt.collected_at, datetime) or receipt.collected_at.tzinfo is None
                or receipt.collected_at.utcoffset() is None):
            raise SchemaError('선착장 원문과 receipt의 출처/버전/해시/시점 불일치')
        try:
            attachment(receipt.download_url, final=True)
        except (AccessDeniedError, SchemaError) as exc:
            raise SchemaError('선착장 receipt의 공식 첨부 identity 오류') from exc
    for number, row in enumerate(_rows(data, max_features), 1):
        if stop.is_set():
            return
        yield OfficialPier(receipt.source if receipt else 'local_csv:' + checksum,
            f'derived:{"20201020" if receipt else "local"}:{checksum}:{number}', number,
            row['선착장명'].strip() or None, row['선착장주소'].strip() or None, MappingProxyType(row),
            checksum, receipt.source_url if receipt else None, receipt.collected_at if receipt else None,
            CONTENT_DATE if receipt else None)


async def iter_pier_file(path: str | Path, *, receipt: PierFileReceipt | None = None,
        batch_size: int = 64, max_features: int = 10000) -> AsyncGenerator[OfficialPier, None]:
    """원 DMS·N/공란/0을 그대로 보존한다. 공식 receipt가 없으면 local_csv다."""
    if (type(batch_size) is not int or not 1 <= batch_size <= 256
            or type(max_features) is not int or not 1 <= max_features <= 10000):
        raise ValueError('batch_size1..256, max_features1..10000 정수가 필요합니다')
    def producer(stop: threading.Event) -> Generator[OfficialPier, None, None]:
        return _records(Path(path), max_features, receipt, stop)
    def estimate(item: OfficialPier) -> int:
        return sum(len(s.encode('utf-8')) * 2 for s in item.raw_attributes.values()) + 512
    async with aclosing(iter_worker(producer, batch_size=batch_size, estimate=estimate)) as stream:
        async for row in stream:
            yield row
