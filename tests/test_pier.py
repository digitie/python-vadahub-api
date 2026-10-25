"""공식 선착장 원문·버전·취소·보관과 수동 검토 도선의 실패 경계를 검증한다."""
import asyncio
from contextlib import aclosing
import csv
from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import urlencode
import pytest
from vadahub import (OfficialPierClient, PierFileReceipt, OfficialPier, pier_to_port,
    reviewed_route_crosswalks, ArchiveReceipt, DatasetLayer, SpatialFeature, LocalArchiveStore,
    AsyncTokenBucket, SchemaError, ArchiveError, AccessDeniedError, map_route)
from vadahub._pier_file import (SOURCE, SOURCE_URL, CONTENT_DATE, NAME, FILENAME, COLUMNS,
    inspect_pier, attachment, _rows)

NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)
ATTACH = ('FILE_000000002322901', '1')
URL = 'https://www.data.go.kr/cmm/cmm/fileDownload.do?' + urlencode(dict(atchFileId=ATTACH[0], fileDetailSn='1', dataNm=NAME))


def csv_bytes(count=2):
    output = io.StringIO(newline=''); writer = csv.writer(output); writer.writerow(COLUMNS)
    for number in range(count):
        row = dict.fromkeys(COLUMNS, '') | {'선착장명': '동명 선착장', '선착장주소': f'주소{number}',
            '위도도': '34', '위도분': '0', '위도초': '', '도선기착지유무': 'N'}
        writer.writerow([row[key] for key in COLUMNS])
    return output.getvalue().encode('cp949')


def receipt(path):
    data = path.read_bytes()
    return PierFileReceipt(SOURCE_URL, URL, NOW, hashlib.sha256(data).hexdigest(), len(data), path)


def wire(browser, monkeypatch, path, *, url=URL, filename=FILENAME):
    monkeypatch.setattr('vadahub.pier._open_portal', AsyncMock(return_value=ATTACH))
    events = {}
    item = SimpleNamespace(url=url, suggested_filename=filename, path=AsyncMock(return_value=path),
        cancel=AsyncMock(), delete=AsyncMock())
    async def click(): events['download'](item)
    button = SimpleNamespace(count=AsyncMock(return_value=1), first=SimpleNamespace(click=AsyncMock(side_effect=click)))
    browser.page.locator = Mock(return_value=button)
    browser.page.on = Mock(side_effect=lambda event, fn: events.__setitem__(event, fn))
    browser.page.remove_listener = Mock(side_effect=lambda event, fn: events.pop(event, None))
    return item, button, events


async def test_download_read_raw_roles_and_unique_derived_ids(browser, monkeypatch, tmp_path):
    path = tmp_path/'input'; path.write_bytes(csv_bytes())
    target = tmp_path/'public.csv'; item, button, events = wire(browser, monkeypatch, path)
    async def delete(): assert not target.exists()
    item.delete.side_effect = delete
    async with OfficialPierClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        result = await client.download(target)
        assert result.source == SOURCE and result.content_date == CONTENT_DATE and result.byte_size == len(path.read_bytes())
        rows = await client.load_file(target, receipt=result)
        assert len(rows) == 2 and len({row.record_id for row in rows}) == 2
        assert all(row.source == SOURCE and row.name == '동명 선착장' for row in rows)
        assert rows[0].raw_attributes['위도분'] == '0' and rows[0].raw_attributes['위도초'] == ''
        assert rows[0].raw_attributes['도선기착지유무'] == 'N'
        with pytest.raises(TypeError): rows[0].raw_attributes['위도도'] = '0'
        port = pier_to_port(rows[0]); assert port.key == (SOURCE, rows[0].record_id) and port.kind == 'pier'
        assert port.latitude is None and port.longitude is None and port.source_year == '2020'
        assert client.rate_limiter is client._browser.rate_limiter
        with pytest.raises(FileExistsError): await client.download(target)
    assert not events and not list(tmp_path.glob('*.part')); item.delete.assert_awaited_once()
    assert '15070386' in browser.page.locator.call_args.args[0]


@pytest.mark.parametrize('kwargs,error', [({'url': URL.replace(ATTACH[0], 'FILE_000000000000001')}, SchemaError),
    ({'filename': NAME + '.csv'}, SchemaError), ({'url': URL.replace(NAME, 'other') + '&dataNm=other'}, SchemaError),
    ({'url': URL.replace('www.data.go.kr', 'evil.example')}, AccessDeniedError)])
async def test_wrong_download_never_published(browser, monkeypatch, tmp_path, kwargs, error):
    path = tmp_path/'input'; path.write_bytes(csv_bytes()); item, _, events = wire(browser, monkeypatch, path, **kwargs)
    async with OfficialPierClient() as client:
        with pytest.raises(error): await client.download(tmp_path/'target')
    assert not (tmp_path/'target').exists() and not events
    item.delete.assert_awaited_once()


async def test_cancellation_during_download_cleanup_preserves_old_success(browser, monkeypatch, tmp_path):
    path = tmp_path/'input'; path.write_bytes(csv_bytes()); item, _, events = wire(browser, monkeypatch, path)
    started, release = asyncio.Event(), asyncio.Event()
    async def delete(): started.set(); await release.wait()
    item.delete.side_effect = delete
    async with OfficialPierClient() as client:
        task = asyncio.create_task(client.download(tmp_path/'target'))
        await started.wait(); task.cancel(); release.set()
        with pytest.raises(asyncio.CancelledError): await task
    assert not (tmp_path/'target').exists() and not list(tmp_path.glob('*.part')) and not events


async def test_file_local_provenance_and_iterator_cleanup(tmp_path, monkeypatch):
    path = tmp_path/'input'; path.write_bytes(csv_bytes())
    async with OfficialPierClient() as client:
        local = await client.load_file(path)
        assert local[0].source.startswith('local_csv:') and local[0].content_date is None
        assert local[0].source_url is None and ':local:' in local[0].record_id
        with pytest.raises(SchemaError): pier_to_port(local[0])
        assert pier_to_port(local[0], kind_evidence='호출자가 검토한 시설').latitude is None
        async with aclosing(client.iter_file(path, receipt=receipt(path), batch_size=1)) as stream:
            assert (await anext(stream)).row_number == 1
        fake_download = AsyncMock(return_value=receipt(path)); monkeypatch.setattr(client, 'download', fake_download)
        assert len(await client.load()) == 2
        assert len([r async for r in client.iter(batch_size=1)]) == 2


@pytest.mark.parametrize('change', [{'source': 'other'}, {'source_url': 'https://evil.example'},
    {'content_date': date(2021, 1, 1)}, {'sha256': '0'*64}, {'byte_size': 1}, {'byte_size': True},
    {'schema_version': '2'}, {'collected_at': datetime(2026, 10, 25)}, {'download_url': URL + '&dataNm=wrong'}])
async def test_forged_receipts_rejected(tmp_path, change):
    path = tmp_path/'input'; path.write_bytes(csv_bytes())
    async with OfficialPierClient() as client:
        with pytest.raises(SchemaError): await client.load_file(path, receipt=replace(receipt(path), **change))


@pytest.mark.parametrize('change', [{'batch_size': True}, {'batch_size': 0}, {'batch_size': 257},
    {'max_features': 0}, {'max_features': 10001}])
async def test_iterator_bounds(tmp_path, change):
    async with OfficialPierClient() as client:
        with pytest.raises(ValueError): await anext(client.iter_file(tmp_path/'missing', **change))


@pytest.mark.parametrize('data', [b'', b'\xff', csv_bytes().replace('선착장명'.encode('cp949'), b'wrong'),
    csv_bytes() + b'broken\r\n', csv_bytes(0), csv_bytes() + b'"unclosed'])
def test_broken_csv_including_trailing_rows(tmp_path, data):
    path = tmp_path/'input'; path.write_bytes(data)
    with pytest.raises(SchemaError): inspect_pier(path)


def test_csv_size_and_row_limits(tmp_path):
    path = tmp_path/'large'
    with path.open('wb') as stream: stream.truncate(16*1024*1024+1)
    with pytest.raises(ArchiveError): inspect_pier(path)
    with pytest.raises(SchemaError): list(_rows(csv_bytes(2), 1))


async def test_store_versions_isolation_recovery_and_corruption(tmp_path):
    path = tmp_path/'input'; path.write_bytes(csv_bytes()); original = receipt(path)
    store = LocalArchiveStore(tmp_path/'store')
    first = await store.put(original)
    assert isinstance(first.receipt, PierFileReceipt) and first.receipt.local_path.name == 'source.csv'
    assert 'official/data-go/15070386/2020-10-20' in first.object_key
    assert (await store.put(original)) == first
    assert (await store.versions(original)) == (first,)
    (store.root/'manifest.json').unlink(); assert len(await store.recover()) == 1
    path.write_bytes(csv_bytes(3)); second = await store.put(receipt(path))
    assert second.receipt.sha256 != first.receipt.sha256 and first.receipt.local_path.read_bytes() == csv_bytes()
    path.write_bytes(b'broken')
    with pytest.raises(ArchiveError): await store.put(receipt(path))
    assert len(await store.versions(original)) == 2
    first.receipt.local_path.write_bytes(b'corrupt')
    with pytest.raises(ArchiveError): await store.versions(original)


@pytest.mark.parametrize('change', [{'source_url': 'https://evil.example'}, {'source': 'bad'},
    {'download_url': 'https://evil.example'}, {'content_date': date(2021, 1, 1)}, {'schema_version': '2'}])
async def test_store_rejects_bad_scope_before_commit(tmp_path, change):
    path = tmp_path/'input'; path.write_bytes(csv_bytes())
    with pytest.raises(ArchiveError): await LocalArchiveStore(tmp_path/'store').put(replace(receipt(path), **change))


def reviewed_fixture():
    from vadahub.reviewed import _REVIEW
    fixture = json.loads((Path(__file__).parent/'fixtures/reviewed_gid2.json').read_text(encoding='utf-8'))
    raw = fixture['feature']; attrs = raw['attributes']; attrs['mfgg_ymd'] = date.fromisoformat(attrs['mfgg_ymd']['date'])
    layer = DatasetLayer('52', '2019-12-10', '500048', 'piltg_rute_l', '도선항로', 'OPEN', 'ALL', True, True, False)
    sha = 'a'*64
    rec = ArchiveReceipt(layer, layer.source_url, NOW, sha, 6992, Path('not-read.zip'), ())
    feature = SpatialFeature(layer, '2', 'gid', MappingProxyType(raw['raw_attributes']), MappingProxyType(attrs),
        bytes.fromhex('010200000002000000cd939ea474232f412c5096532ffa38414800c896b7232f41b949f6c842f83841'),
        'LINESTRING', None, None, None, sha, NOW, True)
    piers = [OfficialPier(SOURCE, f"derived:20201020:{_REVIEW['pier_csv_sha256']}:{target['row_number']}",
        target['row_number'], target['name'], target['address'], MappingProxyType(row),
        _REVIEW['pier_csv_sha256'], SOURCE_URL, NOW, CONTENT_DATE)
        for target, row in zip(_REVIEW['targets'], fixture['piers'], strict=True)]
    return feature, rec, piers


def test_reviewed_pair_current_archive_binding_and_original_missing_preserved():
    feature, rec, piers = reviewed_fixture()
    crosswalk = reviewed_route_crosswalks(feature, receipt=rec, piers=piers)
    result = map_route(feature, ports=[pier_to_port(p) for p in piers], crosswalk=crosswalk, endpoint_kind='pier')
    assert result.departure.port.name == '국동' and result.arrival.port.name == '외동'
    assert result.endpoints.departure is None and result.endpoints.arrival is None
    assert all(port.latitude is None for port in result.ports)
    for sha in ('b'*64, 'c'*64):
        rebound = reviewed_route_crosswalks(replace(feature, source_sha256=sha), receipt=replace(rec, sha256=sha), piers=piers)
        assert rebound[0].source_sha256 == sha and rebound[0].revision == crosswalk[0].revision
    assert reviewed_route_crosswalks(replace(feature, record_id='13'), receipt=rec, piers=[]) == ()


@pytest.mark.parametrize('case', ['sha', 'source', 'time', 'layer_version', 'wkb', 'raw', 'normalized',
    'field', 'geometry_type', 'date_type', 'missing_pier', 'duplicate_pier', 'pier_source', 'pier_version',
    'pier_sha', 'pier_id', 'pier_name', 'pier_address', 'pier_raw', 'pier_time'])
def test_reviewed_rejects_changed_or_forged_record(case):
    f, r, piers = reviewed_fixture()
    if case == 'sha': r = replace(r, sha256='b'*64)
    if case == 'source': r = replace(r, source_url='https://evil.example')
    if case == 'time': f = replace(f, source_collected_at=None)
    if case == 'layer_version': f = replace(f, layer=replace(f.layer, history_date='2020-01-01'))
    if case == 'wkb': f = replace(f, geometry_wkb=f.geometry_wkb[:-1] + b'X')
    if case == 'raw': f = replace(f, raw_attributes=dict(f.raw_attributes) | {'c7': '20220826'})
    if case == 'normalized': f = replace(f, attributes=dict(f.attributes) | {'enc_no': 'KR_OTHER'})
    if case == 'field': f = replace(f, record_id_field='other')
    if case == 'geometry_type': f = replace(f, geometry_type='MULTILINESTRING')
    if case == 'date_type': f = replace(f, attributes=dict(f.attributes) | {'mfgg_ymd': {'date':'2022-08-25'}})
    if case == 'missing_pier': piers = piers[:1]
    if case == 'duplicate_pier': piers += [piers[0]]
    if case == 'pier_source': piers[0] = replace(piers[0], source='other')
    if case == 'pier_version': piers[0] = replace(piers[0], content_date=date(2021,1,1))
    if case == 'pier_sha': piers[0] = replace(piers[0], source_sha256='b'*64)
    if case == 'pier_id': piers[0] = replace(piers[0], record_id='official-government-code')
    if case == 'pier_name': piers[0] = replace(piers[0], name='동명')
    if case == 'pier_address': piers[0] = replace(piers[0], address='다른 주소')
    if case == 'pier_raw': piers[0] = replace(piers[0], raw_attributes=dict(piers[0].raw_attributes) | {'도선기착지유무':'Y'})
    if case == 'pier_time': piers[0] = replace(piers[0], source_collected_at=datetime(2026,10,25))
    with pytest.raises(SchemaError): reviewed_route_crosswalks(f, receipt=r, piers=piers)


def test_reviewed_pier_upper_bound():
    f, r, piers = reviewed_fixture()
    with pytest.raises(SchemaError): reviewed_route_crosswalks(f, receipt=r, piers=(piers[0] for _ in range(10001)))
