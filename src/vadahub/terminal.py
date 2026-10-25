"""공식 공개 CSV를 명시적으로 선택하는 터미널 보완 파일 클라이언트."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import aclosing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from collections.abc import Callable, Awaitable
from typing import TypeVar

from playwright.async_api import BrowserContext, Download, Page, Response, Dialog

from ._terminal_source import NAME, _attachment
from ._browser import BrowserSession
from ._io import run_io
from ._ratelimit import AsyncTokenBucket
from ._terminal_file import SOURCE_URL, MAX_BYTES, inspect_terminal, iter_terminal_file
from .client import _check_status, _ACCESS_ELEMENTS, _ACCESS_TITLE
from .exceptions import AccessDeniedError, ArchiveError, DownloadUnavailableError, ProviderError, SchemaError
from .mapping import PortReference
from .models import PassengerTerminal, TerminalFileReceipt, PierFileReceipt

_BUTTON = 'button[onclick*="fileDetailObj.fn_fileDataDown(\'15148558\'"]'


async def _open_portal(page: Page, *, source_url: str = SOURCE_URL, name: str = NAME,
        attachment: Callable[[str], tuple[str, str]] = _attachment) -> tuple[str, str]:
    response = await page.goto(source_url, wait_until='domcontentloaded')
    if response is None: raise ProviderError('공식 파일 공개 페이지 응답이 없습니다')
    _check_status(response.status)
    if page.url != source_url:
        raise AccessDeniedError('공식 파일 페이지가 다른 경로로 이동했습니다')
    title = await page.title()
    if _ACCESS_TITLE.search(title) or await page.locator(_ACCESS_ELEMENTS).count():
        raise AccessDeniedError('공식 파일의 로그인/보안 확인 화면입니다')
    if name not in title or '공공데이터포털' not in title:
        raise SchemaError('공식 파일 자료명/버전이 바뀌었습니다')
    datasets = []
    texts = await page.locator('script[type="application/ld+json"]').evaluate_all(
        "els => els.length <= 4 && els.every(e => e.textContent.length <= 1048576) ? els.map(e => e.textContent) : null")
    if not isinstance(texts, list):
        raise SchemaError('공식 파일 JSON-LD 크기/개수 상한 초과')
    for text in texts:
        try:
            # 실제 페이지의 설명 문자열에 literal TAB이 있어 strict=False로만 읽힌다.
            item = json.loads(text, strict=False)
        except (ValueError, TypeError, RecursionError) as exc:
            raise SchemaError('공식 파일 JSON-LD 형식 오류') from exc
        if isinstance(item, dict) and item.get('@type') == 'Dataset': datasets.append(item)
    if len(datasets) != 1 or datasets[0].get('url') not in (source_url, source_url.replace('www.', '')):
        raise SchemaError('공식 파일 JSON-LD dataset identity 오류')
    distributions = datasets[0].get('distribution')
    if (not isinstance(distributions, list) or len(distributions) != 1
            or not isinstance(distributions[0], dict) or distributions[0].get('encodingFormat') != 'CSV'
            or not isinstance(distributions[0].get('contentUrl'), str)):
        raise SchemaError('공식 파일 CSV 첨부 schema 오류')
    return attachment(distributions[0]['contentUrl'])


def _stage_csv(source: Path, temporary: Path, *,
        inspect: Callable[[Path], tuple[str, int]] = inspect_terminal) -> tuple[str, int]:
    if source.stat().st_size > MAX_BYTES: raise ArchiveError('공식 CSV16MiB 상한 초과')
    if shutil.disk_usage(temporary.parent).free < source.stat().st_size * 2:
        raise ArchiveError('공식 CSV 검증용 로컬 여유 공간 부족')
    shutil.copyfile(source, temporary)
    result = inspect(temporary)
    with temporary.open('rb+') as stream:
        stream.flush()
        os.fsync(stream.fileno())
    return result


async def _close_download(item: Download) -> None:
    await item.cancel()
    await item.delete()


class OfficialTerminalClient:
    """15148558 고정 공개 CSV 전용. VadaHub 데이터/브라우저 허용범위를 바꾸지 않는다."""
    def __init__(self, *, timeout: float = 60, cleanup_timeout: float = 5, max_rps: float = 1,
            rate_limiter: AsyncTokenBucket | None = None, browser_context: BrowserContext | None = None,
            executable_path: str | None = None) -> None:
        self._browser = BrowserSession(timeout=timeout, cleanup_timeout=cleanup_timeout, max_rps=max_rps,
            rate_limiter=rate_limiter, browser_context=browser_context, executable_path=executable_path,
            provider='official_terminal')

    @property
    def rate_limiter(self) -> AsyncTokenBucket:
        return self._browser.rate_limiter

    async def __aenter__(self) -> OfficialTerminalClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._browser.aclose()

    async def download(self, destination: str | Path) -> TerminalFileReceipt:
        """고정 공개 버튼으로 CSV를 받아 strict 검사·정리 후 신규 경로에 원자 공개한다."""
        return await _download_csv(self._browser, destination, source_url=SOURCE_URL,
            filename=NAME + '.csv', button_selector=_BUTTON, portal=_open_portal,
            attachment=lambda url: _attachment(url, final=True), stage=_stage_csv,
            make_receipt=TerminalFileReceipt)

    def iter_file(self, path: str | Path, *, receipt: TerminalFileReceipt | None = None,
            batch_size: int = 64, max_features: int = 10000) -> AsyncGenerator[PassengerTerminal, None]:
        """로컬 공식/수동 CSV를 bounded OGR worker로 읽는다. 조기 종료는 aclosing을 사용한다."""
        return iter_terminal_file(path, receipt=receipt, batch_size=batch_size, max_features=max_features)

    async def load_file(self, path: str | Path, *, receipt: TerminalFileReceipt | None = None,
            max_features: int = 10000) -> list[PassengerTerminal]:
        return [row async for row in self.iter_file(path, receipt=receipt, max_features=max_features)]

    async def iter(self, *, batch_size: int = 64, max_features: int = 10000) -> AsyncGenerator[PassengerTerminal, None]:
        """공개 CSV→bounded OGR iterator. 종료 시 임시 원문과 worker를 정리한다."""
        with tempfile.TemporaryDirectory(prefix='vadahub-terminal-') as directory:
            receipt = await self.download(Path(directory)/'terminal.csv')
            async with aclosing(self.iter_file(receipt.local_path, receipt=receipt,
                    batch_size=batch_size, max_features=max_features)) as stream:
                async for row in stream: yield row

    async def load(self, *, max_features: int = 10000) -> list[PassengerTerminal]:
        """공식 공개 파일 전체 적재. 영구 원문 보관은 download와 LocalArchiveStore를 사용한다."""
        return [row async for row in self.iter(max_features=max_features)]



_FileReceipt = TypeVar("_FileReceipt", TerminalFileReceipt, PierFileReceipt)


async def _download_csv(browser: BrowserSession, destination: str | Path, *,
        source_url: str, filename: str, button_selector: str,
        portal: Callable[[Page], Awaitable[tuple[str, str]]],
        attachment: Callable[[str], tuple[str, str]],
        stage: Callable[[Path, Path], tuple[str, int]],
        make_receipt: Callable[[str, str, datetime, str, int, Path], _FileReceipt]) -> _FileReceipt:
    """공식 고정 CSV의 같은 생명주기·취소·원자 공개 경계를 공유한다."""
    path = Path(destination).absolute()
    if path.exists(): raise FileExistsError(path)
    await run_io(path.parent.mkdir, 0o777, True, True)
    async with browser.operation() as page:
        expected = await portal(page)
        button = page.locator(button_selector)
        if await button.count() != 1:
            raise DownloadUnavailableError('공식 파일 공개 다운로드 버튼이 없습니다')
        loop = asyncio.get_running_loop()
        received: asyncio.Future[Download] = loop.create_future()
        failure: asyncio.Future[Exception] = loop.create_future()

        def on_download(item: Download) -> None:
            if not received.done(): received.set_result(item)

        def on_response(response: Response) -> None:
            if response.url.startswith('https://www.data.go.kr/') and response.status in (401, 403, 429):
                try: _check_status(response.status)
                except Exception as exc:
                    if not failure.done(): failure.set_result(exc)

        async def on_dialog(dialog: Dialog) -> None:
            if not failure.done(): failure.set_result(ProviderError('공식 파일 UI의 오류/접근 안내'))
            await dialog.dismiss()

        page.on('download', on_download)
        page.on('response', on_response)
        page.on('dialog', on_dialog)
        temporary = None
        item = None
        cleanup_started = False
        try:
            await button.first.click()
            await asyncio.wait((received, failure), return_when=asyncio.FIRST_COMPLETED)
            if failure.done(): raise failure.result()
            item = received.result()
            download_url = item.url
            if attachment(download_url) != expected or item.suggested_filename != filename:
                raise SchemaError('공식 파일 다운로드 파일/첨부 identity가 바뀌었습니다')
            source = await item.path()
            if source is None: raise ArchiveError('공식 CSV의 로컬 다운로드 경로가 없습니다')
            if failure.done(): raise failure.result()
            descriptor, name = tempfile.mkstemp(prefix='.official-csv-', suffix='.part', dir=path.parent)
            os.close(descriptor)
            temporary = Path(name)
            checksum, size = await run_io(stage, Path(source), temporary)
            cleanup_started = True
            task = asyncio.current_task()
            assert task is not None
            cancellation_count = task.cancelling()
            await browser._close_resource(_close_download, item)
            if task.cancelling() != cancellation_count:
                raise asyncio.CancelledError
            if failure.done(): raise failure.result()
            os.link(temporary, path)
            return make_receipt(source_url, download_url, datetime.now(timezone.utc), checksum, size, path)
        finally:
            page.remove_listener('download', on_download)
            page.remove_listener('response', on_response)
            page.remove_listener('dialog', on_dialog)
            if item is None and received.done() and not received.cancelled(): item = received.result()
            received.cancel()
            failure.cancel()
            if temporary is not None: temporary.unlink(missing_ok=True)
            if item is not None and not cleanup_started:
                try: await browser._close_resource(_close_download, item)
                except Exception: pass  # 본래 오류를 보존하며 context 종료로 잔여 원문을 정리한다.


def terminal_to_port(terminal: PassengerTerminal, *, kind_evidence: str | None = None) -> PortReference:
    """출처별 코드와 공식 terminal 역할을 보존한다. 미확인 좌표를 경위도로 승격하지 않는다."""
    evidence = kind_evidence
    if terminal.source == 'data.go.kr:15148558' and terminal.source_url == SOURCE_URL:
        evidence = evidence or SOURCE_URL + '#공간정보일련번호=' + terminal.record_id
    if not evidence or not terminal.name:
        raise SchemaError('터미널 이름과 terminal 역할의 공식/호출자 검토 근거가 필요합니다')
    return PortReference(terminal.source, terminal.record_id, terminal.name, kind='terminal',
        address=terminal.address, collected_at=terminal.source_collected_at, source_url=terminal.source_url,
        source_year=str(terminal.survey_year) if terminal.survey_year is not None else None, kind_evidence=evidence)
