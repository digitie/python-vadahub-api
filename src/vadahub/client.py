"""키 없는 VadaHub 공개 웹 클라이언트의 async 기반."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Literal

from playwright.async_api import BrowserContext, Page

from ._browser import BASE_URL, BrowserSession
from ._ratelimit import AsyncTokenBucket
from .exceptions import AccessDeniedError, NetworkError, RateLimitError, SchemaError
from .models import PageSnapshot
from .models import Dataset, DatasetLayer
from . import _catalog

_SPACE_PATH = "/renew/spaceData/index.do"
_ACCESS_TITLE = re.compile(r"로그인|보안\s*확인|접근\s*(?:제한|거부)|captcha|access denied", re.I)
_ACCESS_ELEMENTS = (
    "input[type='password']:visible, [id*='captcha' i]:visible, "
    "[class*='captcha' i]:visible, iframe[src*='captcha' i]:visible"
)
_POST = """async ({path, data}) => {
 const r=await fetch(path,{method:'POST',redirect:'error',
 headers:{'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'},body:new URLSearchParams(data)});
 if(r.status!==200) return {status:r.status,text:''};
 const reader=r.body.getReader(); let size=0; const chunks=[];
 for(;;){const {done,value}=await reader.read(); if(done) break;
  size+=value.length; if(size>2097152){await reader.cancel();return {status:200,too_large:true};} chunks.push(value);}
 const all=new Uint8Array(size);let n=0;for(const c of chunks){all.set(c,n);n+=c.length;}
 return {status:r.status,text:new TextDecoder('utf-8',{fatal:true}).decode(all)};
}"""


async def _open_page(page: Page, url: str, container: str = '#listForm') -> str:
    response = await page.goto(url, wait_until='domcontentloaded')
    if response is None:
        raise NetworkError('공개 페이지 응답이 없습니다')
    _check_status(response.status)
    if page.url != url:
        raise AccessDeniedError('공개 페이지가 다른 경로로 이동했습니다')
    title = (await page.title()).strip()
    if _ACCESS_TITLE.search(title) or await page.locator(_ACCESS_ELEMENTS).count():
        raise AccessDeniedError('로그인 또는 보안 확인 화면입니다')
    if '해양수산부' not in title or '공동활용체계' not in title:
        raise SchemaError('VadaHub 공개 페이지 제목 계약이 바뀌었습니다')
    if not await page.locator(container).count():
        raise SchemaError('공개 공간자료 페이지의 필수 컨테이너가 없습니다')
    return title


def _check_status(status: int) -> None:
    """접근 거부·한도·네트워크 실패를 빈 성공으로 바꾸지 않는다."""
    if 300 <= status < 400 or status in (401, 403):
        raise AccessDeniedError("공개 웹 접근이 거부되거나 다른 경로로 이동합니다")
    if status == 429:
        raise RateLimitError("공개 웹 호출 제한입니다")
    if status != 200:
        raise NetworkError(f"공개 웹 HTTP {status}")


class VadaHubClient:
    """공개 웹 기반 provider. 첫 operation에서 Chromium을 지연 생성한다.

    기본 1 RPS·burst 1은 operation 예산이며 페이지 자산의 전송량 제한과 다르다.
    주입한 context는 호출자가 닫는다. 새로 만든 page는 라이브러리가 닫는다.
    context를 주입하는 경우 Chromium context여야 한다. 자동 재시도는 없다.
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        cleanup_timeout: float = 5.0,
        max_rps: float = 1.0,
        rate_limiter: AsyncTokenBucket | None = None,
        browser_context: BrowserContext | None = None,
        executable_path: str | None = None,
    ) -> None:
        self._browser = BrowserSession(
            timeout=timeout, cleanup_timeout=cleanup_timeout, max_rps=max_rps, rate_limiter=rate_limiter,
            browser_context=browser_context, executable_path=executable_path,
        )

    @property
    def rate_limiter(self) -> AsyncTokenBucket:
        """다른 클라이언트와 공유할 수 있는 실제 operation 제한기."""
        return self._browser.rate_limiter

    async def __aenter__(self) -> VadaHubClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """진행 중 operation 종료를 기다린 뒤 소유 자원을 멱등 정리한다."""
        await self._browser.aclose()

    async def get_page_snapshot(self, page: Literal["space_data"] = "space_data") -> PageSnapshot:
        """공간자료 공개 페이지의 접근·제목·구조를 검증한다."""
        if page != "space_data":
            raise ValueError("page는 space_data여야 합니다")
        url = BASE_URL + _SPACE_PATH
        async with self._browser.operation() as browser_page:
            title = await _open_page(browser_page, url)
            return PageSnapshot(url, title, datetime.now(timezone.utc))

    async def _post(self, page: Page, path: str, data: dict[str, str | int]) -> dict:
        await self.rate_limiter.acquire()
        result = await page.evaluate(_POST, {'path': path, 'data': data})
        if not isinstance(result, dict) or not isinstance(result.get('status'), int):
            raise SchemaError('웹 전송 응답 계약이 바뀌었습니다')
        _check_status(result['status'])
        if result.get('too_large'):
            raise SchemaError('웹 JSON 2MiB 상한 초과')
        body = result.get('text')
        if not isinstance(body, str):
            raise SchemaError('JSON 원문 누락')
        if body.lstrip().startswith('<'):
            raise AccessDeniedError('공개 웹 JSON 대신 HTML/XML이 반환됐습니다')
        try:
            payload = json.loads(body)
        except ValueError:
            raise SchemaError('잘못된 JSON 응답') from None
        if not isinstance(payload, dict):
            raise SchemaError('JSON 객체 응답이 아닙니다')
        return payload

    async def list_datasets(self, *, page_size: int = 50, max_pages: int = 20) -> tuple[Dataset, ...]:
        """원천 total·중복·고정 수량을 검증해 공간 카탈로그를 끝까지 읽는다."""
        if (isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 200
                or isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 100):
            raise ValueError('page_size 1..200, max_pages 1..100 정수가 필요합니다')
        async with self._browser.operation() as page:
            await _open_page(page, BASE_URL + _SPACE_PATH)
            items: list[Dataset] = []
            seen: set[tuple[str, str]] = set()
            total = None
            for number in range(1, max_pages + 1):
                payload = await self._post(page, '/renew/spaceData/list.do',
                                           {'pageIndex': number, 'pageUnit': page_size, 'pageType': 'page'})
                pagination = payload.get('paginationInfo')
                if not isinstance(pagination, dict):
                    raise SchemaError('카탈로그 total 누락')
                current = _catalog.count(pagination.get('totalRecordCount'))
                if total is not None and total != current:
                    raise SchemaError('카탈로그 조회 중 total이 변경됐습니다')
                total = current
                batch = _catalog.rows(payload)
                if len(batch) > page_size or len(items) + len(batch) > total:
                    raise SchemaError('카탈로그 원천 수량 초과')
                for row in batch:
                    item = _catalog.parse_dataset(row)
                    key = (item.dataset_id, item.history_date)
                    if key in seen:
                        raise SchemaError('중복 카탈로그 이력입니다')
                    seen.add(key)
                    items.append(item)
                if len(items) == total:
                    return tuple(items)
                if not batch:
                    raise SchemaError('카탈로그 중간 빈 페이지')
            raise SchemaError('카탈로그 페이지 상한에 도달했습니다')

    async def _layers(self, page: Page, meta: str, hist: str) -> tuple[DatasetLayer, ...]:
        payload = await self._post(page, '/renew/selectMdMetaRelateList.do', {'metaSn': meta, 'histDe': hist})
        batch = _catalog.rows(payload)
        if len(batch) != _catalog.count(payload.get('resultListTotCnt')):
            raise SchemaError('기초자료 수량 불일치')
        items = tuple(_catalog.parse_layer(row, meta, hist) for row in batch)
        if len({item.layer_id for item in items}) != len(items):
            raise SchemaError('중복 기초자료 ID입니다')
        return items

    async def list_layers(self, dataset: Dataset) -> tuple[DatasetLayer, ...]:
        """발견한 meta의 정확한 이력에서 기초자료를 조회한다."""
        meta, hist = _catalog.identifier(dataset.dataset_id), _catalog.history(dataset.history_date)
        async with self._browser.operation() as page:
            await _open_page(page, BASE_URL + _SPACE_PATH)
            return await self._layers(page, meta, hist)

    async def get_availability(self, layer: DatasetLayer) -> DatasetLayer:
        """저장된 상태를 믿지 않고 원천의 현재 layer 상태를 다시 조회한다."""
        meta, hist = _catalog.identifier(layer.dataset_id), _catalog.history(layer.history_date)
        sid = _catalog.identifier(layer.layer_id)
        async with self._browser.operation() as page:
            await _open_page(page, BASE_URL + _SPACE_PATH)
            for current in await self._layers(page, meta, hist):
                if current.layer_id == sid:
                    return current
            raise SchemaError('요청한 layer가 현재 meta 이력에 없습니다')
