"""CP949 원문·native WKT의 실제 GDAL/worker 경계를 검증한다."""
import asyncio
from contextlib import aclosing
import csv
from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import io
import threading
from urllib.parse import urlencode
from vadahub._terminal_source import NAME
import pytest
pytest.importorskip('osgeo', reason='필수 spatial CI/WSL에서 GDAL 실행')
pytestmark = pytest.mark.spatial
from osgeo import ogr
from vadahub import OfficialTerminalClient, TerminalFileReceipt, SchemaError, terminal_to_port
from vadahub._terminal_file import COLUMNS, SOURCE_URL


def fixture_file(tmp_path, count=1, **change):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(COLUMNS)
    for i in range(count):
        attrs = dict.fromkeys(COLUMNS, '') | {'공간정보일련번호': f'{i:03}', '종착지명': '공식 터미널',
            '시설도로명주소': '시설 주소', '여객터미널조사년도': '2014', '공간정보': 'POINT (941840 1884629)'} | change
        writer.writerow([attrs[key] for key in COLUMNS])
    data = stream.getvalue().encode('cp949')
    path = tmp_path/'terminal.csv'; path.write_bytes(data)
    receipt = TerminalFileReceipt(SOURCE_URL, 'https://www.data.go.kr/cmm/cmm/fileDownload.do?' + urlencode(dict(atchFileId='FILE_000000003250090', fileDetailSn='1', dataNm=NAME)),
        datetime.now(timezone.utc), hashlib.sha256(data).hexdigest(), len(data), path)
    return path, receipt


async def test_gdal_features_and_port_provenance(tmp_path):
    path, receipt = fixture_file(tmp_path)
    async with OfficialTerminalClient() as client:
        rows = await client.load_file(path, receipt=receipt)
        local = await client.load_file(path)
    row = rows[0]
    assert row.source == 'data.go.kr:15148558' and row.record_id == '000' and row.survey_year == 2014
    assert row.name == '공식 터미널' and row.source_collected_at == receipt.collected_at
    assert row.geometry_valid and row.source_crs is None and row.geometry_wkb
    with pytest.raises(TypeError): row.raw_attributes['공간정보'] = 'other'
    port = terminal_to_port(row)
    assert port.key == ('data.go.kr:15148558', '000') and port.kind == 'terminal' and port.latitude is None
    assert local[0].source == 'local_csv:'+receipt.sha256 and local[0].source_url is None


@pytest.mark.parametrize('wkt', ['', 'POINT EMPTY'])
async def test_null_geometry_is_not_zero(tmp_path, wkt):
    path, _ = fixture_file(tmp_path, 공간정보=wkt, 종착지명='', 여객터미널조사년도='')
    async with OfficialTerminalClient() as client: row = (await client.load_file(path))[0]
    assert row.geometry_wkb is None and row.geometry_valid is None and row.name is None and row.survey_year is None


@pytest.mark.parametrize('wkt', ['garbage', 'LINESTRING (0 0,1 1)', 'POINT (NaN 1)', 'POINT Z (1 2 3)', 'POINT (1 2) junk', 'POINT (1 2), POINT (3 4)', 'POINTEMPTY', 'POINT (1 2 3)', 'POINT (1e999 2)'])
async def test_bad_geometry_is_explicit(tmp_path, wkt):
    path, _ = fixture_file(tmp_path, 공간정보=wkt)
    async with OfficialTerminalClient() as client:
        with pytest.raises(SchemaError): await client.load_file(path)


@pytest.mark.parametrize('change', [{'sha256': 'b'*64}, {'byte_size': 1}, {'source_url': 'https://evil'},
    {'source': 'other'}, {'content_date': date(2015, 1, 1)}, {'collected_at': datetime(2026, 1, 1)},
    {'download_url': 'https://evil.example/other.csv'},
    {'download_url': 'https://www.data.go.kr/cmm/cmm/fileDownload.do'},
    {'download_url': 'https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003250090&fileDetailSn=1&dataNm=other'}])
async def test_receipt_mismatch(tmp_path, change):
    path, receipt = fixture_file(tmp_path)
    async with OfficialTerminalClient() as client:
        with pytest.raises(SchemaError): await client.load_file(path, receipt=replace(receipt, **change))


@pytest.mark.parametrize('kwargs', [{'batch_size': 0}, {'batch_size': True}, {'max_features': 10001}])
async def test_iterator_limits(tmp_path, kwargs):
    async with OfficialTerminalClient() as client:
        with pytest.raises(ValueError):
            async for _ in client.iter_file(tmp_path/'missing', **kwargs): pass


async def test_row_cap_and_worker_early_close(tmp_path, monkeypatch):
    path, receipt = fixture_file(tmp_path, 200)
    thread_ids = []
    original = ogr.CreateGeometryFromWkt
    def track(*args):
        thread_ids.append(threading.get_ident())
        return original(*args)
    monkeypatch.setattr(ogr, 'CreateGeometryFromWkt', track)
    async with OfficialTerminalClient() as client:
        with pytest.raises(SchemaError): await client.load_file(path, max_features=1)
        thread_ids.clear()
        async with aclosing(client.iter_file(path, receipt=receipt, batch_size=1)) as rows:
            assert (await anext(rows)).record_id == '000'
    assert len(set(thread_ids)) == 1 and thread_ids[0] != threading.get_ident()
    assert len(thread_ids) < 200


async def test_cancel_waits_for_native_worker(tmp_path, monkeypatch):
    path, _ = fixture_file(tmp_path, 10)
    entered, release = threading.Event(), threading.Event()
    original = ogr.CreateGeometryFromWkt
    def block(*args):
        entered.set(); release.wait(5)
        return original(*args)
    monkeypatch.setattr(ogr, 'CreateGeometryFromWkt', block)
    async with OfficialTerminalClient() as client:
        task = asyncio.create_task(client.load_file(path))
        await asyncio.to_thread(entered.wait, 3)
        assert entered.is_set()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError): await task
