"""카탈로그 완전성·명시적 오류·다운로드 공개의 실패 경계를 검증한다."""
import asyncio
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import zipfile

import pytest
from vadahub import (ArchiveError, ArchiveLimits, AsyncTokenBucket, Dataset, DatasetLayer,
                     DownloadUnavailableError, SchemaError, VadaHubFileClient, VadaHubClient,
                     AccessDeniedError, RateLimitError, NetworkError)
from vadahub import _catalog
from vadahub._archive import inspect_archive
from vadahub._io import run_io
from vadahub.files import _publish

META = {'metaSn':52,'histDe':'2019-12-10','metaNm':'도선항로','factorCn12':'설명'}
ROW = {'metaSn':52,'histDe':'2019-12-10','bsisDtaSn':500048,'relateDtaNm':'piltg_rute_l',
       'bsisDtaNm':'도선항로','serviceAuthCd':'OPEN','opnScopeSe':'ALL','gridOpenYn':'Y','dwldPosblYn':'Y'}
DATASET = _catalog.parse_dataset(META)
LAYER = _catalog.parse_layer(ROW,'52','2019-12-10')


def wire(payload):
    return {'status':200,'text':json.dumps(payload)}


def catalog(rows, total):
    return {'resultList':rows,'paginationInfo':{'totalRecordCount':total}}


def client(cls=VadaHubClient, **kwargs):
    return cls(rate_limiter=AsyncTokenBucket(100000), **kwargs)


async def test_catalog_pagination_and_layer_refresh(browser):
    browser.page.evaluate = AsyncMock(side_effect=[wire(catalog([META],2)),wire(catalog([{**META,'metaSn':63}],2)),
            wire({'resultList':[ROW],'resultListTotCnt':1}),wire({'resultList':[{**ROW,'dwldPosblYn':'N'}],'resultListTotCnt':1})])
    async with client() as c:
        datasets = await c.list_datasets(page_size=1)
        assert [x.dataset_id for x in datasets] == ['52','63']
        layers = await c.list_layers(datasets[0])
        assert layers == (LAYER,)
        assert not (await c.get_availability(LAYER)).download_available


@pytest.mark.parametrize('payloads', [
    [catalog([META],2),catalog([],2)], [catalog([META],2),catalog([META],2)],
    [catalog([META],2),catalog([{**META,'metaSn':63}],3)],
    [catalog([META,META],1)], [{'resultList':[]}],
])
async def test_catalog_never_returns_partial_or_duplicates(browser,payloads):
    browser.page.evaluate = AsyncMock(side_effect=list(map(wire,payloads)))
    async with client() as c:
        with pytest.raises(SchemaError):
            await c.list_datasets(page_size=1)


async def test_page_cap_and_empty_catalog(browser):
    browser.page.evaluate = AsyncMock(side_effect=[wire(catalog([META],2)),wire(catalog([],0))])
    async with client() as c:
        with pytest.raises(SchemaError,match='상한'):
            await c.list_datasets(page_size=1,max_pages=1)
        assert await c.list_datasets() == ()


@pytest.mark.parametrize('kwargs',[{'page_size':True},{'page_size':0},{'page_size':201},{'max_pages':0},{'max_pages':True}])
async def test_invalid_pagination_no_network(browser,kwargs):
    async with client() as c:
        with pytest.raises(ValueError): await c.list_datasets(**kwargs)
    browser.manager.start.assert_not_awaited()


@pytest.mark.parametrize('response,error',[
    ({'status':403},AccessDeniedError),({'status':429},RateLimitError),({'status':500},NetworkError),
    ({'status':200,'too_large':True},SchemaError),({'status':200,'text':'<html>login'},AccessDeniedError),
    ({'status':200,'text':'{bad'},SchemaError),({'status':200,'text':'[]'},SchemaError),
    ({'status':200},SchemaError),({},SchemaError),
])
async def test_bad_web_payloads_are_not_empty_success(browser,response,error):
    browser.page.evaluate = AsyncMock(return_value=response)
    async with client() as c:
        with pytest.raises(error): await c.list_datasets()


@pytest.mark.parametrize('mutation',[
    {'metaSn':True},{'metaSn':'../../'},{'histDe':'2026-13-10'},{'histDe':'20261024'},
    {'metaNm':''},{'metaSn':None},{'factorCn12':{}},
])
def test_dataset_validation(mutation):
    with pytest.raises(SchemaError): _catalog.parse_dataset({**META,**mutation})


@pytest.mark.parametrize('mutation',[
    {'metaSn':63},{'histDe':'2020-01-01'},{'relateDtaNm':'a;b'},{'gridOpenYn':None},
    {'dwldPosblYn':'yes'},{'bsisDtaNm':''},
])
def test_layer_validation(mutation):
    with pytest.raises(SchemaError): _catalog.parse_layer({**ROW,**mutation},'52','2019-12-10')


@pytest.mark.parametrize('payload',[
    {'resultList':[ROW],'resultListTotCnt':2}, {'resultList':[ROW,ROW],'resultListTotCnt':2},
    {'resultList':None,'resultListTotCnt':0}, {'resultList':[1],'resultListTotCnt':1},
    {'resultList':[],'resultListTotCnt':True},
])
async def test_invalid_layer_list(browser,payload):
    browser.page.evaluate = AsyncMock(return_value=wire(payload))
    async with client() as c:
        with pytest.raises(SchemaError): await c.list_layers(DATASET)


async def test_missing_layer_is_error(browser):
    browser.page.evaluate = AsyncMock(return_value=wire({'resultList':[],'resultListTotCnt':0}))
    async with client() as c:
        with pytest.raises(SchemaError): await c.get_availability(LAYER)


def test_shared_context_uses_same_session_lock(browser):
    first=client(VadaHubFileClient,browser_context=browser.context)
    second=client(VadaHubFileClient,browser_context=browser.context)
    assert first._browser._lock is second._browser._lock


def make_zip(path, names=None, content=b'abc'):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names or [LAYER.table_name+e for e in ('.shp','.shx','.dbf','.txt')]:
            info=zipfile.ZipInfo()
            info.filename=name
            z.writestr(info,content,compress_type=zipfile.ZIP_DEFLATED)


@pytest.mark.parametrize('names,limits',[
    (['../x'],ArchiveLimits()), (['/x'],ArchiveLimits()), (['C:/x'],ArchiveLimits()),
    (['a\\b'],ArchiveLimits()), (['a','A'],ArchiveLimits()), (['dir/'],ArchiveLimits()),
    (['a','b'],ArchiveLimits(members=1)), (['a'],ArchiveLimits(member_bytes=1)),
    (['a','b'],ArchiveLimits(expanded_bytes=5)),
])
def test_archive_preflight(tmp_path,names,limits):
    p=tmp_path/'x.zip'; make_zip(p,names)
    with pytest.raises(ArchiveError): inspect_archive(p,limits)


def test_archive_hash_sidecar_and_publish_preserves_existing(tmp_path):
    source=tmp_path/'source.zip'; make_zip(source)
    checksum,members=inspect_archive(source,ArchiveLimits(),LAYER.table_name)
    assert checksum==hashlib.sha256(source.read_bytes()).hexdigest() and len(members)==4
    target=tmp_path/'target.zip'
    assert _publish(source,target,LAYER.table_name,ArchiveLimits())[0]==checksum
    before=target.read_bytes()
    with pytest.raises(FileExistsError): _publish(source,target,LAYER.table_name,ArchiveLimits())
    assert target.read_bytes()==before and not list(tmp_path.glob('*.part'))
    with pytest.raises(ArchiveError): inspect_archive(source,ArchiveLimits(),'wrong_table')
    source.write_text('<html>not zip')
    with pytest.raises(ArchiveError): inspect_archive(source,ArchiveLimits())
    with pytest.raises(ArchiveError): inspect_archive(target,ArchiveLimits(archive_bytes=1))


@pytest.mark.parametrize('value',[0,True,-1])
def test_bad_zip_limits(value):
    with pytest.raises(ValueError): ArchiveLimits(members=value)


async def test_download_unavailable_rechecked_and_no_overwrite(browser,tmp_path):
    browser.page.evaluate=AsyncMock(return_value=wire({'resultList':[{**ROW,'dwldPosblYn':'N'}],'resultListTotCnt':1}))
    async with client(VadaHubFileClient) as c:
        with pytest.raises(DownloadUnavailableError): await c.download(LAYER,tmp_path/'x.zip')
        (tmp_path/'old.zip').write_bytes(b'previous')
        with pytest.raises(FileExistsError): await c.download(LAYER,tmp_path/'old.zip')
    assert (tmp_path/'old.zip').read_bytes()==b'previous'


async def test_download_real_state_machine_with_synthetic_browser(browser,tmp_path):
    source=tmp_path/'browser.zip'; make_zip(source)
    browser.page.evaluate=AsyncMock(return_value=wire({'resultList':[ROW],'resultListTotCnt':1}))
    handlers={}
    browser.page.on=Mock(side_effect=lambda event,handler: handlers.__setitem__(event,handler))
    browser.page.remove_listener=Mock(side_effect=lambda event,handler: handlers.pop(event,None))
    async def goto(url,**kwargs): browser.page.url=url; return SimpleNamespace(status=200)
    browser.page.goto.side_effect=goto
    download=SimpleNamespace(path=AsyncMock(return_value=source),cancel=AsyncMock(),delete=AsyncMock())
    button=SimpleNamespace(count=AsyncMock(return_value=1))
    button.first=SimpleNamespace(is_visible=AsyncMock(return_value=False),click=AsyncMock(side_effect=lambda: handlers['download'](download)))
    original=browser.page.locator
    browser.page.locator=Mock(side_effect=lambda sel:button if 'shpDown' in sel else original(sel))
    browser.page.get_by_role=Mock(return_value=SimpleNamespace(click=AsyncMock()))
    async with client(VadaHubFileClient) as c:
        receipt=await c.download(LAYER,tmp_path/'published.zip')
        assert receipt.local_path.read_bytes()==source.read_bytes() and receipt.layer==LAYER
        assert receipt.collected_at.tzinfo and len(receipt.member_sha256)==4
    assert handlers=={}
    download.delete.assert_awaited_once()


async def test_io_cancellation_waits_for_worker_before_cleanup():
    import threading
    started,release=threading.Event(),threading.Event()
    def work(): started.set(); release.wait(); return 'done'
    task=asyncio.create_task(run_io(work))
    await asyncio.to_thread(started.wait)
    task.cancel(); await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError): await task
