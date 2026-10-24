"""공개 UI로 ZIP을 받아 검증 후 호출자가 지정한 경로에 원자 공개한다."""
import asyncio
from datetime import datetime, timezone
from dataclasses import replace
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Literal
from collections.abc import AsyncGenerator

from playwright.async_api import Download, Response, Dialog, Page, Locator

from ._archive import ArchiveLimits, inspect_archive
from ._browser import BASE_URL
from ._catalog import identifier, history
from ._io import run_io
from .client import VadaHubClient, _open_page, _SPACE_PATH, _check_status
from .exceptions import AccessDeniedError, ArchiveError, DownloadUnavailableError, ProviderError, SchemaError
from .models import ArchiveReceipt, DatasetLayer, SpatialFeature
from .models import LibraryResource, LibraryArchiveReceipt
from . import parse


def _stage(source: Path, temporary: Path, table: str | None, limits: ArchiveLimits) -> tuple:
    if source.stat().st_size > limits.archive_bytes:
        raise ArchiveError('다운로드 원문 크기 제한 초과')
    if shutil.disk_usage(temporary.parent).free < source.stat().st_size * 2:
        raise ArchiveError('검증·공개용 로컬 여유 공간 부족')
    shutil.copyfile(source, temporary)
    checksum, members = inspect_archive(temporary, limits, table, allow_directories=table is None)
    return checksum, members, temporary.stat().st_size


async def _cleanup_download(item: Download, timeout: float) -> None:
    try:
        async with asyncio.timeout(timeout):
            await item.cancel()
            await item.delete()
    except Exception:
        pass  # context 종료도 브라우저 임시 원문을 정리한다.


class VadaHubFileClient(VadaHubClient):
    """카탈로그와 같은 세션에서 create→download를 직렬화하는 파일 클라이언트."""

    def iter_file(self, path: str | Path, *, layer: DatasetLayer, source_crs: str | None = None,
                  encoding: str | None = None, batch_size: int = 64, max_features: int = 1000000,
                  limits: ArchiveLimits = ArchiveLimits(), receipt: ArchiveReceipt | None = None,
                  invalid_geometry: Literal['raise','preserve'] = 'raise') -> AsyncGenerator[SpatialFeature, None]:
        """로컬 ZIP을 동일 GDAL 파서로 읽는다. 조기 종료 시 aclose/aclosing을 사용한다."""
        return parse.iter_file(path, layer=layer, source_crs=source_crs, encoding=encoding,
                               batch_size=batch_size, max_features=max_features, limits=limits, receipt=receipt,invalid_geometry=invalid_geometry)

    async def load_file(self, path: str | Path, *, layer: DatasetLayer, source_crs: str | None = None,
                        encoding: str | None = None, max_features: int = 1000000,
                        limits: ArchiveLimits = ArchiveLimits(), receipt: ArchiveReceipt | None = None,
                        invalid_geometry: Literal['raise','preserve'] = 'raise') -> list[SpatialFeature]:
        """로컬 원문 전체를 명시적으로 메모리에 적재한다."""
        return [item async for item in self.iter_file(path, layer=layer, source_crs=source_crs,
                encoding=encoding, max_features=max_features, limits=limits, receipt=receipt,invalid_geometry=invalid_geometry)]

    async def iter(self, layer: DatasetLayer, *, source_crs: str | None = None, encoding: str | None = None,
                   batch_size: int = 64, max_features: int = 1000000,
                   limits: ArchiveLimits = ArchiveLimits(),invalid_geometry: Literal['raise','preserve'] = 'raise') -> AsyncGenerator[SpatialFeature, None]:
        """공개 ZIP→bounded GDAL iterator. 임시 원문은 generator 종료 후 정리한다."""
        from contextlib import aclosing
        with tempfile.TemporaryDirectory(prefix='vadahub-load-') as directory:
            receipt = await self.download(layer, Path(directory) / 'source.zip', limits=limits)
            async with aclosing(self.iter_file(receipt.local_path, layer=receipt.layer, source_crs=source_crs,
                    encoding=encoding, batch_size=batch_size, max_features=max_features, limits=limits, receipt=receipt,invalid_geometry=invalid_geometry)) as stream:
                async for item in stream:
                    yield item

    async def load(self, layer: DatasetLayer, *, source_crs: str | None = None, encoding: str | None = None,
                   max_features: int = 1000000, limits: ArchiveLimits = ArchiveLimits(),
                   invalid_geometry: Literal['raise','preserve'] = 'raise') -> list[SpatialFeature]:
        """공개 ZIP 전체 적재. 원문 보관은 download 또는 후속 store를 사용한다."""
        return [item async for item in self.iter(layer, source_crs=source_crs, encoding=encoding,
                                                max_features=max_features, limits=limits,invalid_geometry=invalid_geometry)]

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
            if layer.require_public:
                if current.service_auth != 'OPEN' or current.open_scope != 'ALL' or current.masked is not False:
                    raise AccessDeniedError('공개/전체/비마스킹 API 공간 layer만 다운로드합니다')
                current = replace(current,require_public=True)
            if not current.download_available:
                raise DownloadUnavailableError('이 layer는 원천에서 다운로드를 제공하지 않습니다')
            await _open_page(page, current.source_url, '#metaSn')
            button = page.locator(f'button[onclick*="shpDown({sid},"]')
            if not await button.count():
                raise DownloadUnavailableError('공개 다운로드 버튼이 없습니다')
            if not await button.first.is_visible():
                await page.get_by_role('button', name='전체보기').click()
            checksum, members, size = await self._download_zip(page,button,path,current.table_name,limits)
            return ArchiveReceipt(current,current.source_url,datetime.now(timezone.utc),checksum,size,path,members)

    async def download_library(self, resource: LibraryResource, destination: str | Path, *,
                               limits: ArchiveLimits = ArchiveLimits()) -> LibraryArchiveReceipt:
        """실제 확인한 연안기본조사 공개 ZIP 버튼만 사용한다. PDF 미리보기는 다운로드하지 않는다."""
        path = Path(destination).absolute()
        if path.exists():
            raise FileExistsError(path)
        await run_io(path.parent.mkdir,0o777,True,True)
        async with self._browser.operation() as page:
            current = await self._current_resource(page,resource)
            if (current.dataset.catalog != 'documents' or current.dataset.dataset_id != '700101'
                    or not current.download_available or not current.source_name.startswith('CoastalBasicSurvey')
                    or not current.source_name.endswith('.zip')):
                raise DownloadUnavailableError('검증한 공개 자료실 ZIP 다운로드가 아닙니다')
            meta, hist, rid = identifier(current.dataset.dataset_id), history(current.dataset.history_date), identifier(current.resource_id)
            source_url = BASE_URL + f'/renew/docData/detail.do?metaSn={meta}&histDe={hist}'
            await _open_page(page,source_url,'#metaSn')
            button = page.locator(f'button[onclick*="zipDown(\'{rid}\',"]')
            if not await button.count():
                raise DownloadUnavailableError('자료실 공개 ZIP 버튼이 없습니다')
            if not await button.first.is_visible():
                await page.get_by_role('button',name='전체보기').click()
            checksum,members,size = await self._download_zip(page,button,path,None,limits)
            return LibraryArchiveReceipt(current,source_url,datetime.now(timezone.utc),checksum,size,path,members)

    async def _download_zip(self, page: Page, button: Locator, path: Path, table: str | None, limits: ArchiveLimits) -> tuple:
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
        temporary = None
        cleaned = False
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
            fd, name = tempfile.mkstemp(prefix='.vadahub-', suffix='.part', dir=path.parent)
            os.close(fd)
            temporary = Path(name)
            checksum, members, size = await run_io(_stage, Path(source), temporary, table, limits)
            # worker 완료·취소 반영과 모든 await 정리 뒤에만 원자 commit한다.
            await _cleanup_download(item, self._browser.cleanup_timeout)
            cleaned = True
            item = None
            if failure.done():
                raise failure.result()
            os.link(temporary, path)
            return checksum, members, size
        finally:
            page.remove_listener('download', on_download)
            page.remove_listener('response', on_response)
            page.remove_listener('dialog', on_dialog)
            if not cleaned and item is None and received.done() and not received.cancelled():
                item = received.result()
            received.cancel()
            failure.cancel()
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if item is not None:
                await _cleanup_download(item, self._browser.cleanup_timeout)
