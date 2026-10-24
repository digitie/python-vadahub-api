"""키 없는 VadaHub 공개 웹 클라이언트의 async 기반."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Literal

from playwright.async_api import BrowserContext

from ._browser import BASE_URL, BrowserSession
from ._ratelimit import AsyncTokenBucket
from .exceptions import AccessDeniedError, NetworkError, RateLimitError, SchemaError
from .models import PageSnapshot

_SPACE_PATH = "/renew/spaceData/index.do"
_ACCESS_TITLE = re.compile(r"로그인|보안\s*확인|접근\s*(?:제한|거부)|captcha|access denied", re.I)
_ACCESS_ELEMENTS = (
    "input[type='password']:visible, [id*='captcha' i]:visible, "
    "[class*='captcha' i]:visible, iframe[src*='captcha' i]:visible"
)


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
        max_rps: float = 1.0,
        rate_limiter: AsyncTokenBucket | None = None,
        browser_context: BrowserContext | None = None,
        executable_path: str | None = None,
    ) -> None:
        self._browser = BrowserSession(
            timeout=timeout, max_rps=max_rps, rate_limiter=rate_limiter,
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
        """공간자료 공개 페이지의 접근·제목·구조를 검증한다. 데이터 목록 API는 T003에서 제공한다."""
        if page != "space_data":
            raise ValueError("page는 space_data여야 합니다")
        url = BASE_URL + _SPACE_PATH
        async with self._browser.operation() as browser_page:
            response = await browser_page.goto(url, wait_until="domcontentloaded")
            if response is None:
                raise NetworkError("공개 페이지 응답이 없습니다")
            _check_status(response.status)
            if browser_page.url != url:
                raise AccessDeniedError("공개 페이지가 다른 경로로 이동했습니다")
            title = (await browser_page.title()).strip()
            if _ACCESS_TITLE.search(title) or await browser_page.locator(_ACCESS_ELEMENTS).count():
                raise AccessDeniedError("로그인 또는 보안 확인 화면입니다")
            if "해양수산부" not in title or "공동활용체계" not in title:
                raise SchemaError("VadaHub 공개 페이지 제목 계약이 바뀌었습니다")
            if not await browser_page.locator("#listForm").count():
                raise SchemaError("공개 공간자료 페이지의 필수 컨테이너가 없습니다")
            return PageSnapshot(url, title, datetime.now(timezone.utc))
