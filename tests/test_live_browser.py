"""실제 Chromium과 VadaHub에서 키 없는 패키지 경계를 검증한다."""

import os
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.parse import urlsplit

from playwright.async_api import async_playwright
import pytest

from vadahub import VadaHubClient, OfficialTerminalClient, ClientClosedError, NetworkError

pytestmark = pytest.mark.live


async def test_owned_browser_keyless_public_page_and_close():
    client = VadaHubClient(executable_path=os.getenv("VADAHUB_CHROMIUM_EXECUTABLE"), timeout=60)
    async with client:
        result = await client.get_page_snapshot()
        assert result.source_url == "https://vadahub.go.kr/renew/spaceData/index.do"
        assert "해양수산부" in result.title
        assert result.collected_at.tzinfo is not None
        print(f"공개 페이지 접근 성공: {result.source_url}, {result.collected_at.isoformat()}")
    with pytest.raises(ClientClosedError):
        await client.get_page_snapshot()


async def test_injected_context_remains_usable_after_client_closes():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=os.getenv("VADAHUB_CHROMIUM_EXECUTABLE"),
        )
        try:
            context = await browser.new_context(service_workers="block")
            try:
                original_pages = len(context.pages)
                async with VadaHubClient(browser_context=context, timeout=60) as client:
                    snapshot = await client.get_page_snapshot("space_data")
                    assert "공동활용체계" in snapshot.title
                    assert len(context.pages) == original_pages + 1
                assert len(context.pages) == original_pages
                extra = await context.new_page()
                await extra.close()
                assert browser.is_connected()
            finally:
                await context.close()
        finally:
            await browser.close()


@pytest.mark.parametrize('provider,client_type', [('vadahub', VadaHubClient), ('official_terminal', OfficialTerminalClient)])
async def test_redirect_each_hop_is_filtered_before_network(monkeypatch, provider, client_type):
    """실제 Chromium이 차단 대상 redirect를 서버에 전송하지 않는지 확인한다."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.path)
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/forbidden")
            elif self.path == "/allowed-start":
                self.send_response(302)
                self.send_header("Location", "/ok")
            else:
                self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    authority = f"localhost:{server.server_port}"
    from vadahub._browser import _allowed_resource
    seen_providers = []
    def allowed(url, kind, *, provider='vadahub'):
        seen_providers.append(provider)
        if urlsplit(url).netloc == authority:
            return kind.lower() == 'document'
        return _allowed_resource(url, kind, provider=provider)
    monkeypatch.setattr('vadahub._browser._allowed_resource', allowed)
    try:
        async with client_type(executable_path=os.getenv("VADAHUB_CHROMIUM_EXECUTABLE")) as client:
            with pytest.raises(NetworkError):
                async with client._browser.operation() as page:
                    await page.goto(f"http://{authority}/start")
            async with client._browser.operation() as page:
                response = await page.goto(f"http://{authority}/allowed-start")
                assert response.status == 200
        assert received == ["/start", "/allowed-start", "/ok"]
        assert seen_providers and set(seen_providers) == {provider}
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        await asyncio.to_thread(worker.join)
