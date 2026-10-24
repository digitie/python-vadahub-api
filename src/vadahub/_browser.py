"""Chromium의 지연 생성, 직렬 operation, 소유권과 취소 정리."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
import math
from typing import Any, TypeVar
from urllib.parse import urlsplit
from weakref import WeakKeyDictionary

from playwright.async_api import (
    BrowserContext,
    CDPSession,
    Error as PlaywrightError,
    Page,
    async_playwright,
)

from ._ratelimit import AsyncTokenBucket
from .exceptions import ClientClosedError, NetworkError

BASE_URL = "https://vadahub.go.kr"
T = TypeVar("T")
_CONTEXT_LOCKS: WeakKeyDictionary[BrowserContext, asyncio.Lock] = WeakKeyDictionary()


def _allowed_resource(raw_url: str, resource_type: str) -> bool:
    """소유 page의 허용 origin·자원 종류를 판정한다."""
    url = urlsplit(raw_url)
    return (
        url.scheme == "https"
        and url.netloc == "vadahub.go.kr"
        and resource_type.lower() in {"document", "script", "stylesheet", "xhr", "fetch"}
    )


async def _intercept_request(session: CDPSession, event: dict[str, Any]) -> None:
    """리디렉션을 포함한 각 전송 전에 Chromium 요청을 종결한다."""
    request_id = event["requestId"]
    try:
        if _allowed_resource(event["request"]["url"], event["resourceType"]):
            await session.send("Fetch.continueRequest", {"requestId": request_id})
        else:
            await session.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
    except PlaywrightError:
        # page 종료로 자동 detach된 session에는 더 이상 전송할 요청이 없다.
        return


class BrowserSession:
    """하나의 이벤트 루프에서 사용하는 내부 Chromium 세션."""

    def __init__(
        self,
        *,
        timeout: float,
        cleanup_timeout: float,
        max_rps: float,
        rate_limiter: AsyncTokenBucket | None,
        browser_context: BrowserContext | None,
        executable_path: str | None,
    ) -> None:
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout은 유한한 양수여야 합니다")
        if isinstance(cleanup_timeout, bool) or not math.isfinite(cleanup_timeout) or cleanup_timeout <= 0:
            raise ValueError("cleanup_timeout은 유한한 양수여야 합니다")
        if browser_context is not None and executable_path is not None:
            raise ValueError("browser_context와 executable_path는 함께 지정할 수 없습니다")
        self.timeout = float(timeout)
        self.cleanup_timeout = float(cleanup_timeout)
        self.rate_limiter = rate_limiter or AsyncTokenBucket(max_rps, capacity=1)
        self._external_context = browser_context
        self._executable_path = executable_path
        self._page: Page | None = None
        self._stack: AsyncExitStack | None = None
        # 동일 주입 context는 서버 cookie/session을 공유하므로 서로 다른 SDK도 직렬화한다.
        self._lock = (asyncio.Lock() if browser_context is None
                      else _CONTEXT_LOCKS.setdefault(browser_context, asyncio.Lock()))
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False
        self._pending: set[asyncio.Task[Any]] = set()

    def _bind_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError("VadaHubClient는 한 이벤트 루프에서 사용해야 합니다")

    async def _ensure_page(self) -> Page:
        if self._page is not None:
            return self._page
        self._stack = AsyncExitStack()
        context = self._external_context
        if context is None:
            playwright = await self._acquire(async_playwright().start(), lambda value: value.stop())
            browser = await self._acquire(
                playwright.chromium.launch(executable_path=self._executable_path),
                lambda value: value.close(),
            )
            context = await self._acquire(
                browser.new_context(service_workers="block"), lambda value: value.close(),
            )
        session: CDPSession | None = None

        async def close_page(value: Page) -> None:
            try:
                await value.close()
            finally:
                if session is not None:
                    session.remove_listener("Fetch.requestPaused", intercept)
                    try:
                        await session.detach()
                    except PlaywrightError:
                        pass  # page.close가 이미 session을 detach한 경우

        async def intercept(event: dict[str, Any]) -> None:
            assert session is not None
            await _intercept_request(session, event)

        page = await self._acquire(context.new_page(), close_page)
        # page를 닫으면 생성 도중의 CDP session도 함께 해제된다.
        session = await context.new_cdp_session(page)
        session.on("Fetch.requestPaused", intercept)
        await session.send("Network.setBypassServiceWorker", {"bypass": True})
        await session.send("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
        page.set_default_timeout(self.timeout * 1000)
        self._page = page
        return page

    async def _acquire(self, creation: Awaitable[T], close: Callable[[T], Awaitable[None]]) -> T:
        # 취소 후에도 짧은 정리 유예만 기다리고, 늦은 생성 결과의 소유권은 계속 추적한다.
        task = asyncio.ensure_future(creation)
        try:
            resource = await asyncio.shield(task)
        except asyncio.CancelledError:
            if not task.cancelled():
                await self._wait_cleanup(task)
                if not task.done():
                    self._closed = True
                    self._defer_acquisition(task, close)
                elif not task.cancelled():
                    try:
                        resource = task.result()
                    except Exception:
                        pass  # 취소 뒤 생성 실패는 원래 취소를 가리지 않는다.
                    else:
                        assert self._stack is not None
                        self._stack.push_async_callback(self._close_resource, close, resource)
            raise
        assert self._stack is not None
        self._stack.push_async_callback(self._close_resource, close, resource)
        return resource

    async def _wait_cleanup(self, task: asyncio.Task[Any]) -> None:
        """반복 취소로 연장되지 않는 절대 정리 유예. 원격 command 자체는 취소하지 않는다."""
        deadline = asyncio.get_running_loop().time() + self.cleanup_timeout
        while not task.done():
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return
            try:
                await asyncio.wait({task}, timeout=remaining)
            except asyncio.CancelledError:
                continue

    def _track_cleanup(self, task: asyncio.Task[Any]) -> None:
        self._pending.add(task)

        def finished(done: asyncio.Task[Any]) -> None:
            self._pending.discard(done)
            if not done.cancelled():
                done.exception()  # 유예 뒤 실패도 미회수 task 오류로 남기지 않는다.

        task.add_done_callback(finished)

    def _defer_acquisition(self, task: asyncio.Task[T], close: Callable[[T], Awaitable[None]]) -> None:
        """늦게 반환된 자원도 닫는다. 멈춘 외부 context를 SDK가 닫지는 않는다."""
        self._pending.add(task)

        def acquired(done: asyncio.Task[T]) -> None:
            self._pending.discard(done)
            if done.cancelled():
                return
            try:
                resource = done.result()
            except Exception:
                return
            self._track_cleanup(asyncio.create_task(self._close_resource(close, resource)))

        task.add_done_callback(acquired)

    async def _close_resource(self, close: Callable[[T], Awaitable[None]], resource: T) -> None:
        task = asyncio.ensure_future(close(resource))
        await self._wait_cleanup(task)
        if not task.done():
            self._closed = True
            self._track_cleanup(task)
            raise NetworkError("브라우저 정리 유예를 초과했습니다. 늦은 종료는 계속 추적합니다")
        if task.cancelled():
            raise NetworkError("브라우저 자원 정리 command가 취소됐습니다")
        await task

    async def _dispose(self) -> None:
        stack, self._stack = self._stack, None
        self._page = None
        if stack is None:
            return
        # 취소가 반복돼도 page/context/browser/driver 정리가 끝날 때까지 기다린다.
        task = asyncio.create_task(stack.aclose())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not task.cancelled():
                task.exception()
            raise

    @asynccontextmanager
    async def operation(self) -> AsyncIterator[Page]:
        """동시 navigation을 막고 operation마다 공유 예산을 적용한다."""
        self._bind_loop()
        try:
            async with asyncio.timeout(self.timeout):
                async with self._lock:
                    if self._closed:
                        raise ClientClosedError("종료된 클라이언트입니다")
                    await self.rate_limiter.acquire()
                    try:
                        yield await self._ensure_page()
                    except BaseException as exc:
                        try:
                            await self._dispose()
                        except Exception:
                            self._closed = True
                            exc.add_note("브라우저 정리가 실패하여 클라이언트를 종료했습니다")
                        if isinstance(exc, PlaywrightError):
                            raise NetworkError("Chromium 시작 또는 공개 페이지 통신 실패") from None
                        raise
        except TimeoutError:
            raise NetworkError("Chromium operation 시간 제한을 초과했습니다") from None

    async def aclose(self) -> None:
        """진행 중 operation을 기다린 뒤 소유 자원만 닫는다."""
        self._bind_loop()
        async with self._lock:
            self._closed = True
            try:
                await self._dispose()
            except PlaywrightError:
                raise NetworkError("Chromium 자원 정리 실패") from None
