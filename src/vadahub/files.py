"""공개 UI로 ZIP을 받아 검증 후 호출자가 지정한 경로에 원자 공개한다."""
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from playwright.async_api import Download, Response, Dialog

from ._archive import ArchiveLimits, inspect_archive
from ._browser import BASE_URL
from ._catalog import identifier, history
from ._io import run_io
from .client import VadaHubClient, _open_page, _SPACE_PATH, _check_status
from .exceptions import ArchiveError, DownloadUnavailableError, ProviderError, SchemaError
from .models import ArchiveReceipt, DatasetLayer


def _publish(source: Path, destination: Path, table: str, limits: ArchiveLimits) -> tuple:
    if source.stat().st_size > limits.archive_bytes:
        raise ArchiveError('다운로드 원문 크기 제한 초과')
    if shutil.disk_usage(destination.parent).free < source.stat().st_size * 2:
        raise ArchiveError('검증·공개용 로컬 여유 공간 부족')
    fd, name = tempfile.mkstemp(prefix='.vadahub-', suffix='.part', dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        shutil.copyfile(source, temporary)
        checksum, members = inspect_archive(temporary, limits, table)
        size = temporary.stat().st_size
        os.link(temporary, destination)
        return checksum, members, size
    finally:
        temporary.unlink(missing_ok=True)


class VadaHubFileClient(VadaHubClient):
    """카탈로그와 같은 세션에서 create→download를 직렬화하는 파일 클라이언트."""

    async def download(self, layer: DatasetLayer, destination: str | Path, *,
                       limits: ArchiveLimits = ArchiveLimits()) -> ArchiveReceipt:
        """공개 버튼이 있는 ZIP만 받는다. 기존 경로는 기본으로 덮어쓰지 않는다.

        수신 후 크기 제한이며 브라우저 임시 디스크의 수신 전 제한을 보장하지 않는다.
        로컬 Chromium context만 지원한다(원격 연결의 download.path는 지원하지 않는다).
        """
        meta, hist, sid = identifier(layer.dataset_id), history(layer.history_date), identifier(layer.layer_id)
        path = Path(destination).absolute()
        if path.exists():
            raise FileExistsError(path)
        await run_io(path.parent.mkdir, 0o777, True, True)
        async with self._browser.operation() as page:
            await _open_page(page, BASE_URL + _SPACE_PATH)
            current = next((x for x in await self._layers(page, meta, hist) if x.layer_id == sid), None)
            if current is None or current.table_name != layer.table_name:
                raise SchemaError('기초자료가 없거나 layer identity가 달라졌습니다')
            if not current.download_available:
                raise DownloadUnavailableError('이 layer는 원천에서 다운로드를 제공하지 않습니다')
            await _open_page(page, current.source_url, '#metaSn')
            button = page.locator(f'button[onclick*="shpDown({sid},"]')
            if not await button.count():
                raise DownloadUnavailableError('공개 다운로드 버튼이 없습니다')
            if not await button.first.is_visible():
                await page.get_by_role('button', name='전체보기').click()
            loop = asyncio.get_running_loop()
            received: asyncio.Future[Download] = loop.create_future()
            failure: asyncio.Future[Exception] = loop.create_future()

            def on_download(item: Download) -> None:
                if not received.done():
                    received.set_result(item)

            def on_response(response: Response) -> None:
                if response.url.startswith(BASE_URL + '/') and response.status in (401, 403, 429):
                    try:
                        _check_status(response.status)
                    except Exception as exc:
                        if not failure.done():
                            failure.set_result(exc)

            async def on_dialog(dialog: Dialog) -> None:
                if not failure.done():
                    failure.set_result(ProviderError('다운로드 UI가 오류/접근 안내를 표시했습니다'))
                await dialog.dismiss()

            page.on('download', on_download)
            page.on('response', on_response)
            page.on('dialog', on_dialog)
            item = None
            try:
                await button.first.click()
                waiters: list[asyncio.Future[Any]] = [received, failure]
                await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
                if failure.done():
                    raise failure.result()
                item = received.result()
                source = await item.path()
                if source is None:
                    raise ArchiveError('다운로드 파일 경로가 없습니다')
                if failure.done():
                    raise failure.result()
                checksum, members, size = await run_io(_publish, Path(source), path, current.table_name, limits)
                return ArchiveReceipt(current, current.source_url, datetime.now(timezone.utc), checksum, size, path, members)
            finally:
                page.remove_listener('download', on_download)
                page.remove_listener('response', on_response)
                page.remove_listener('dialog', on_dialog)
                received.cancel()
                failure.cancel()
                if item is not None:
                    try:
                        async with asyncio.timeout(self._browser.cleanup_timeout):
                            await item.cancel()
                            await item.delete()
                    except Exception:
                        pass  # context 종료도 브라우저 임시 원문을 정리한다.
