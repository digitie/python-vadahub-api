"""공식 보완 원천의 브라우저 경계·원자 다운로드·CSV 구조 실패를 검증한다."""
import asyncio
import csv
from contextlib import aclosing
from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import urlencode
import pytest
from vadahub import (OfficialTerminalClient, AsyncTokenBucket, SchemaError, AccessDeniedError,
    ArchiveError, DownloadUnavailableError, RateLimitError, PassengerTerminal, terminal_to_port,
    TerminalFileReceipt, LocalArchiveStore)
from vadahub._browser import _allowed_resource, _intercept_request, BrowserSession
from vadahub._terminal_file import COLUMNS, SOURCE_URL, inspect_terminal, _rows
from vadahub.terminal import NAME, _attachment, _open_portal, _stage_csv

ATTACH = ('FILE_000000003250090', '1')
URL = 'https://www.data.go.kr/cmm/cmm/fileDownload.do?' + urlencode(dict(atchFileId=ATTACH[0], fileDetailSn='1', dataNm=NAME))


def csv_bytes(count=1, **changes):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(COLUMNS)
    for number in range(count):
        row = dict.fromkeys(COLUMNS, '') | {'공간정보일련번호': str(number + 1), '종착지명': '원문 터미널',
            '시설도로명주소': '공개 시설 주소', '여객터미널조사년도': '2014', '공간정보': 'POINT (941840 1884629)'} | changes
        writer.writerow([row[key] for key in COLUMNS])
    return output.getvalue().encode('cp949')


def wire_download(browser, monkeypatch, source, *, item_url=URL, suggested=NAME+'.csv'):
    from vadahub import terminal
    monkeypatch.setattr(terminal, '_open_portal', AsyncMock(return_value=ATTACH))
    events = {}
    item = SimpleNamespace(url=item_url, suggested_filename=suggested,
        path=AsyncMock(return_value=source), cancel=AsyncMock(), delete=AsyncMock())
    async def click(): events['download'](item)
    button = SimpleNamespace(count=AsyncMock(return_value=1), first=SimpleNamespace(click=AsyncMock(side_effect=click)))
    browser.page.locator = Mock(return_value=button)
    browser.page.on = Mock(side_effect=lambda event, fn: events.__setitem__(event, fn))
    browser.page.remove_listener = Mock(side_effect=lambda event, fn: events.pop(event, None))
    return item, button, events


async def test_atomic_csv_download_and_cleanup_before_publish(browser, monkeypatch, tmp_path):
    source = tmp_path/'source.csv'; source.write_bytes(csv_bytes())
    target = tmp_path/'terminal.csv'
    item, _, events = wire_download(browser, monkeypatch, source)
    async def delete(): assert not target.exists()
    item.delete.side_effect = delete
    async with OfficialTerminalClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        receipt = await client.download(target)
        assert receipt.source == 'data.go.kr:15148558' and receipt.source_url == SOURCE_URL
        assert receipt.sha256 == inspect_terminal(source)[0] and receipt.collected_at.tzinfo is not None
        assert target.read_bytes() == source.read_bytes() and not list(tmp_path.glob('*.part')) and events == {}
        assert client.rate_limiter is client._browser.rate_limiter
        with pytest.raises(FileExistsError): await client.download(target)
    item.delete.assert_awaited_once()


@pytest.mark.parametrize('change,error', [({'item_url': 'https://evil.example/file'}, AccessDeniedError),
    ({'suggested': 'other.csv'}, SchemaError), ({'item_url': URL.replace(ATTACH[0], 'FILE_000000000000001')}, SchemaError)])
async def test_wrong_source_never_published(browser, monkeypatch, tmp_path, change, error):
    source = tmp_path/'source'; source.write_bytes(csv_bytes())
    item, _, events = wire_download(browser, monkeypatch, source, **change)
    async with OfficialTerminalClient() as client:
        with pytest.raises(error): await client.download(tmp_path/'target')
    assert not (tmp_path/'target').exists() and not events
    item.delete.assert_awaited_once()


@pytest.mark.parametrize('status,error', [(403, AccessDeniedError), (429, RateLimitError)])
async def test_http_denial_not_empty_file(browser, monkeypatch, tmp_path, status, error):
    item, button, events = wire_download(browser, monkeypatch, tmp_path/'unused')
    async def click():
        events['response'](SimpleNamespace(url=URL, status=status))
        events['download'](item)
    button.first.click.side_effect = click
    async with OfficialTerminalClient() as client:
        with pytest.raises(error): await client.download(tmp_path/'target')
    item.delete.assert_awaited_once()
    assert not (tmp_path/'target').exists()


async def test_cancel_during_download_cleanup_cannot_commit(browser, monkeypatch, tmp_path):
    source = tmp_path/'source'; source.write_bytes(csv_bytes())
    item, _, _ = wire_download(browser, monkeypatch, source)
    started, release = asyncio.Event(), asyncio.Event()
    async def delete():
        started.set()
        await release.wait()
    item.delete.side_effect = delete
    async with OfficialTerminalClient() as client:
        task = asyncio.create_task(client.download(tmp_path/'target'))
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError): await task
    assert not (tmp_path/'target').exists() and not list(tmp_path.glob('*.part'))
    item.delete.assert_awaited_once()


async def test_cleanup_failure_and_bad_csv_do_not_commit(browser, monkeypatch, tmp_path):
    source = tmp_path/'source'; source.write_bytes(csv_bytes())
    item, _, _ = wire_download(browser, monkeypatch, source)
    item.delete.side_effect = RuntimeError('delete failed')
    async with OfficialTerminalClient() as client:
        with pytest.raises(RuntimeError): await client.download(tmp_path/'target')
    assert not (tmp_path/'target').exists() and not list(tmp_path.glob('*.part'))
    source.write_bytes(b'HTML error')
    item, _, _ = wire_download(browser, monkeypatch, source)
    async with OfficialTerminalClient() as client:
        with pytest.raises(SchemaError): await client.download(tmp_path/'target')
    item.delete.assert_awaited_once()


async def test_no_button_or_no_received_path(browser, monkeypatch, tmp_path):
    item, button, _ = wire_download(browser, monkeypatch, tmp_path/'unused')
    button.count.return_value = 0
    async with OfficialTerminalClient() as client:
        with pytest.raises(DownloadUnavailableError): await client.download(tmp_path/'target')
    item, _, _ = wire_download(browser, monkeypatch, tmp_path/'unused')
    item.path.return_value = None
    async with OfficialTerminalClient() as client:
        with pytest.raises(ArchiveError): await client.download(tmp_path/'target')


@pytest.mark.parametrize('url', ['https://[', 'https://www.data.go.kr.evil/cmm/cmm/fileDownload.do',
    'http://www.data.go.kr/cmm/cmm/fileDownload.do', URL+'#fragment', URL+'\n'])
def test_attachment_origin_rejects(url):
    with pytest.raises(AccessDeniedError): _attachment(url)


@pytest.mark.parametrize('url', [URL+'&fileDetailSn=2', URL+'&extra=x', URL.replace('fileDetailSn=1', 'fileDetailSn=0'),
    URL.replace('FILE_', 'OTHER_'), URL.replace('dataNm=', 'other='), URL+'&insertDataPrcus=Y',
    URL.replace('atchFileId=', 'x=')])
def test_attachment_identity_rejects(url):
    with pytest.raises(SchemaError): _attachment(url, final=True)


async def test_origin_policies_do_not_expand_each_other(browser):
    assert _allowed_resource(SOURCE_URL, 'Document', provider='official_terminal')
    assert not _allowed_resource(SOURCE_URL, 'Document')
    assert not _allowed_resource('https://vadahub.go.kr/x', 'Fetch', provider='official_terminal')
    assert not _allowed_resource('https://[', 'Document')
    assert not _allowed_resource(SOURCE_URL, 'Image', provider='official_terminal')
    event = {'requestId': 'x', 'request': {'url': 'https://vadahub.go.kr/x'}, 'resourceType': 'Document'}
    await _intercept_request(browser.session, event, provider='official_terminal')
    assert browser.session.send.await_args.args[0] == 'Fetch.failRequest'
    with pytest.raises(ValueError): BrowserSession(timeout=1, cleanup_timeout=1, max_rps=1,
        rate_limiter=None, browser_context=None, executable_path=None, provider='evil')
    async with OfficialTerminalClient(browser_context=browser.context) as client:
        async with client._browser.operation(): pass
    browser.context.close.assert_not_awaited()


def test_csv_integrity_and_limits(tmp_path, monkeypatch):
    path = tmp_path/'raw'; path.write_bytes(csv_bytes())
    assert inspect_terminal(path)[1] == path.stat().st_size
    for data in [b'\x81', b'wrong,header\n', csv_bytes(0), csv_bytes(2, 공간정보일련번호='1'),
        csv_bytes(공간정보일련번호='x'), csv_bytes(여객터미널조사년도='20x4')]:
        path.write_bytes(data)
        with pytest.raises(SchemaError): inspect_terminal(path)
    path.write_bytes(csv_bytes(2))
    with pytest.raises(SchemaError): list(_rows(path.read_bytes(), 1))
    monkeypatch.setattr('vadahub._terminal_file.MAX_BYTES', 1)
    with pytest.raises(ArchiveError): inspect_terminal(path)


def test_local_terminal_requires_reviewed_role():
    row = PassengerTerminal('local_csv:a', '001', '이름', '주소', 2014, {}, None, None, 'a'*64, None, None)
    with pytest.raises(SchemaError): terminal_to_port(row)
    port = terminal_to_port(row, kind_evidence='reviewed facility record')
    assert port.key == ('local_csv:a', '001') and port.kind == 'terminal' and port.latitude is None


async def test_public_portal_metadata_validation(browser):
    page = browser.page
    page.url = SOURCE_URL
    page.title.return_value = NAME + ' | 공공데이터포털'
    document = {'@type': 'Dataset', 'url': SOURCE_URL.replace('www.', ''), 'distribution': [
        {'encodingFormat': 'CSV', 'contentUrl': URL}]}
    scripts = SimpleNamespace(evaluate_all=AsyncMock(return_value=[json.dumps(document)]))
    access = SimpleNamespace(count=AsyncMock(return_value=0))
    page.locator = Mock(side_effect=lambda selector: scripts if selector.startswith('script[') else access)
    assert await _open_portal(page) == ATTACH
    for value in [None, ['{invalid'], [json.dumps(document | {'url': 'https://evil'})],
        [json.dumps(document | {'distribution': []})], [json.dumps(document)]*2]:
        scripts.evaluate_all.return_value = value
        with pytest.raises(SchemaError): await _open_portal(page)
    scripts.evaluate_all.return_value = [json.dumps(document)]
    page.title.return_value = '로그인'
    with pytest.raises(AccessDeniedError): await _open_portal(page)
    page.title.return_value = '다른 자료'
    with pytest.raises(SchemaError): await _open_portal(page)
    page.title.return_value = NAME + ' | 공공데이터포털'
    page.url = 'https://evil'
    with pytest.raises(AccessDeniedError): await _open_portal(page)
    page.url = SOURCE_URL
    page.goto.return_value = None
    with pytest.raises(Exception, match='응답'): await _open_portal(page)


def test_csv_short_columns_and_stage_resource_limits(tmp_path, monkeypatch):
    data = csv_bytes().decode('cp949').splitlines()[0] + '\n1,2\n'
    with pytest.raises(SchemaError): list(_rows(data.encode('cp949'), 10))
    data = csv_bytes().decode('cp949').splitlines()[0] + '\n"unterminated'
    with pytest.raises(SchemaError): list(_rows(data.encode('cp949'), 10))
    source = tmp_path/'raw'; source.write_bytes(csv_bytes())
    monkeypatch.setattr('vadahub.terminal.MAX_BYTES', 1)
    with pytest.raises(ArchiveError): _stage_csv(source, tmp_path/'stage')
    monkeypatch.setattr('vadahub.terminal.MAX_BYTES', 16*1024*1024)
    monkeypatch.setattr('vadahub.terminal.shutil.disk_usage', lambda p: SimpleNamespace(free=0))
    with pytest.raises(ArchiveError): _stage_csv(source, tmp_path/'stage')


def terminal_receipt(tmp_path):
    path = tmp_path/'source.csv'; data = csv_bytes(); path.write_bytes(data)
    return TerminalFileReceipt(SOURCE_URL, URL, datetime.now(timezone.utc), hashlib.sha256(data).hexdigest(), len(data), path)


async def test_official_csv_store_versions_and_orphan_recovery(tmp_path, monkeypatch):
    receipt = terminal_receipt(tmp_path)
    store = LocalArchiveStore(tmp_path/'store')
    stored = await store.put(receipt)
    assert stored == await store.put(receipt) and await store.versions(receipt) == (stored,)
    assert isinstance(stored.receipt, TerminalFileReceipt) and stored.receipt.local_path.name == 'source.csv'
    assert stored.object_key.startswith('objects/official/data-go/15148558/2014-12-31/')
    assert stored.content_fingerprint == receipt.sha256 and await store.recover() == ()
    import vadahub.storage as module
    other_store = LocalArchiveStore(tmp_path/'orphan')
    original = module._atomic_json
    def fail(path, value):
        if path.name == 'manifest.json': raise OSError('manifest failed')
        return original(path, value)
    monkeypatch.setattr(module, '_atomic_json', fail)
    with pytest.raises(OSError): await other_store.put(receipt)
    monkeypatch.setattr(module, '_atomic_json', original)
    recovered = await other_store.recover()
    assert len(recovered) == 1 and await other_store.versions(receipt) == recovered
    stored.receipt.local_path.write_bytes(csv_bytes(종착지명='수정된 원문'))
    with pytest.raises(ArchiveError): await store.versions(receipt)
    stored.receipt.local_path.write_bytes(b'invalid CSV')
    with pytest.raises(ArchiveError): await store.recover()


@pytest.mark.parametrize('change', [{'source_url': 'https://evil'}, {'download_url': 'https://evil'},
    {'content_date': date(2015, 1, 1)}, {'collected_at': datetime(2026, 1, 1)}, {'byte_size': True},
    {'sha256': 'b'*64}, {'source': 'other'}])
async def test_official_store_bad_receipt(tmp_path, change):
    receipt = terminal_receipt(tmp_path)
    store = LocalArchiveStore(tmp_path/'store')
    with pytest.raises(ArchiveError): await store.put(replace(receipt, **change))
    assert not (store.root/'manifest.json').exists()


async def test_download_iter_closes_worker_before_temporary_file(monkeypatch):
    closed = []
    locations = []
    async with OfficialTerminalClient() as client:
        async def download(path):
            path.write_bytes(csv_bytes())
            locations.append(path)
            return TerminalFileReceipt(SOURCE_URL, URL, datetime.now(timezone.utc), 'a'*64, 1, path)
        async def records(path, **kwargs):
            assert kwargs['receipt'].local_path == path and kwargs['max_features'] == 3
            try:
                row = PassengerTerminal('local', '001', '터미널', None, 2014, {}, None, None, 'a'*64, None, None)
                yield row
                yield row
            finally:
                assert path.exists()
                closed.append(True)
        monkeypatch.setattr(client, 'download', download)
        monkeypatch.setattr(client, 'iter_file', records)
        async with aclosing(client.iter(batch_size=1, max_features=3)) as stream:
            assert (await anext(stream)).record_id == '001'
        assert closed == [True] and not locations[0].exists()
        assert len(await client.load(max_features=3)) == 2
        assert closed == [True, True] and not locations[1].exists()
