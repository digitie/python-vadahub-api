"""고정 공식 선착장 파일의 async 수집·원문 계보·시설 참조."""
from __future__ import annotations
from collections.abc import AsyncGenerator
from contextlib import aclosing
from functools import partial
from pathlib import Path
import tempfile

from playwright.async_api import BrowserContext
from ._browser import BrowserSession
from ._ratelimit import AsyncTokenBucket
from ._pier_file import SOURCE, SOURCE_URL, NAME, FILENAME, CONTENT_DATE, attachment, inspect_pier, iter_pier_file
from .exceptions import SchemaError
from .mapping import PortReference
from .models import OfficialPier, PierFileReceipt
from .terminal import _download_csv, _open_portal, _stage_csv


class OfficialPierClient:
    """15070386/20201020 고정 공개 CSV. 파생 ID는 정부 항구코드가 아니다."""
    def __init__(self, *, timeout: float = 60, cleanup_timeout: float = 5, max_rps: float = 1,
            rate_limiter: AsyncTokenBucket | None = None, browser_context: BrowserContext | None = None,
            executable_path: str | None = None) -> None:
        self._browser = BrowserSession(timeout=timeout, cleanup_timeout=cleanup_timeout, max_rps=max_rps,
            rate_limiter=rate_limiter, browser_context=browser_context, executable_path=executable_path,
            provider='official_terminal')

    @property
    def rate_limiter(self) -> AsyncTokenBucket:
        return self._browser.rate_limiter

    async def __aenter__(self) -> OfficialPierClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._browser.aclose()

    async def download(self, destination: str | Path) -> PierFileReceipt:
        """현재 공식 버튼/첨부·버전을 대조한 후 신규 경로에 원자 공개한다."""
        return await _download_csv(self._browser, destination, source_url=SOURCE_URL, filename=FILENAME,
            button_selector='button[onclick*="fileDetailObj.fn_fileDataDown(\'15070386\'"]',
            portal=partial(_open_portal, source_url=SOURCE_URL, name=NAME, attachment=attachment),
            attachment=partial(attachment, final=True), stage=partial(_stage_csv, inspect=inspect_pier),
            make_receipt=PierFileReceipt)

    def iter_file(self, path: str | Path, *, receipt: PierFileReceipt | None = None,
            batch_size: int = 64, max_features: int = 10000) -> AsyncGenerator[OfficialPier, None]:
        return iter_pier_file(path, receipt=receipt, batch_size=batch_size, max_features=max_features)

    async def load_file(self, path: str | Path, *, receipt: PierFileReceipt | None = None,
            max_features: int = 10000) -> list[OfficialPier]:
        return [row async for row in self.iter_file(path, receipt=receipt, max_features=max_features)]

    async def iter(self, *, batch_size: int = 64, max_features: int = 10000) -> AsyncGenerator[OfficialPier, None]:
        """공개 파일의 bounded worker. 조기 종료는 aclosing으로 감싼다."""
        with tempfile.TemporaryDirectory(prefix='vadahub-pier-') as directory:
            receipt = await self.download(Path(directory)/'pier.csv')
            async with aclosing(self.iter_file(receipt.local_path, receipt=receipt,
                    batch_size=batch_size, max_features=max_features)) as stream:
                async for row in stream:
                    yield row

    async def load(self, *, max_features: int = 10000) -> list[OfficialPier]:
        return [row async for row in self.iter(max_features=max_features)]


def pier_to_port(pier: OfficialPier, *, kind_evidence: str | None = None) -> PortReference:
    """원천별 파생 키와 물리 선착장 역할을 유지하고 미선언 DMS는 변환하지 않는다."""
    evidence = kind_evidence
    if pier.source == SOURCE and pier.source_url == SOURCE_URL and pier.content_date == CONTENT_DATE:
        evidence = evidence or SOURCE_URL + '#derived-row=' + str(pier.row_number)
    if not evidence or not pier.name:
        raise SchemaError('선착장 이름과 공식/호출자 검토 역할 근거가 필요합니다')
    return PortReference(pier.source, pier.record_id, pier.name, kind='pier', address=pier.address,
        collected_at=pier.source_collected_at, source_url=pier.source_url,
        source_year=str(pier.content_date.year) if pier.content_date else None, kind_evidence=evidence)
