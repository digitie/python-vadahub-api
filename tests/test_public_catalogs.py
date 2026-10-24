"""공개 안내/자료실의 식별·접근·미리보기·ZIP 계약을 검증한다."""
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import json
import zipfile
import pytest
from vadahub import (Dataset, VadaHubFileClient, ArchiveError, ArchiveLimits, LibraryArchiveReceipt,
    LocalArchiveStore, SchemaError, AccessDeniedError, DownloadUnavailableError)
from vadahub import _catalog
from vadahub._archive import inspect_archive

META={'metaSn':700101,'histDe':'2025-12-30','metaNm':'연안기본조사','factorCn12':None}
DATASET=_catalog.parse_dataset(META,'documents')
ROW=dict(metaSn=700101,histDe='2025-12-30',bsisDtaSn=720006,bsisDtaNm='연안환경',
    relateDtaNm='CoastalBasicSurvey01.zip',orginlTableNm='PDF',atrbSpceSe='PDF',serviceAuthCd='OPEN',
    opnScopeSe='ALL',gridOpenYn='Y',dwldPosblYn='Y',maskingYn='N')
RESOURCE=_catalog.parse_resource(ROW,DATASET)


def wire(value): return {'status':200,'text':json.dumps(value)}
def related(row=ROW):return {'resultList':[row],'resultListTotCnt':1}


def prepare(browser,payloads):
    async def goto(url,**kwargs):
        browser.page.url=url
        return SimpleNamespace(status=200)
    browser.page.goto.side_effect=goto
    browser.page.evaluate=AsyncMock(side_effect=[wire(p) for p in payloads])


@pytest.mark.parametrize('kind',['documents','statistics','api_original','api_analysis','api_map'])
async def test_catalog_family_and_api_identity(browser,kind):
    rows=[META]
    if kind.startswith('api_'):
        rows=[META|{'odtaId':'141'},META|{'odtaId':'142','odtaReqstUrl':'https://example.org/info','extsnType':'JSON'}]
    prepare(browser,[{'paginationInfo':{'totalRecordCount':len(rows)},'resultList':rows}])
    async with VadaHubFileClient() as client:
        values=await client.list_datasets(catalog=kind)
        assert len(values)==len(rows) and values[0].catalog==kind
        if kind.startswith('api_'):
            assert values[1].api_id=='142' and 'metaSn=5248' in values[1].source_url
            assert 'odtaId=142' in values[1].source_url and values[1].dataset_id=='700101'
        with pytest.raises(ValueError):await client.list_layers(values[0])
        with pytest.raises(ValueError):await client.list_datasets(catalog='invalid')
    assert browser.page.evaluate.await_args_list[0].args[1]['path']==_catalog.CATALOG_PATHS[kind][1]


async def test_resource_identity_counts_and_flags(browser):
    prepare(browser,[related()])
    async with VadaHubFileClient() as client:
        assert await client.list_resources(DATASET)==(RESOURCE,)
        with pytest.raises(ValueError): await client.list_resources(replace(DATASET,catalog='space'))
    for change in ({'metaSn':1},{'maskingYn':'bad'},{'atrbSpceSe':None},{'relateDtaNm':''}):
        with pytest.raises(SchemaError):_catalog.parse_resource(ROW|change,DATASET)


@pytest.mark.parametrize('payload',[{'resultList':[ROW],'resultListTotCnt':2},{'resultList':[ROW,ROW],'resultListTotCnt':2}])
async def test_resource_bad_totals_and_duplicate(browser,payload):
    prepare(browser,[payload])
    async with VadaHubFileClient() as client:
        with pytest.raises(SchemaError):await client.list_resources(DATASET)


async def test_document_preview_is_separate_from_download(browser):
    row=ROW|{'dwldPosblYn':'N','relateDtaNm':'자료.pdf'}
    resource=_catalog.parse_resource(row,DATASET)
    prepare(browser,[related(row),{'fileYn':'Y','pdfFile':'/resource/publish/pdf/test/자료.pdf'}])
    async with VadaHubFileClient() as client:
        result=await client.get_document_preview(resource)
    assert not result.resource.download_available and result.preview_url.endswith('/자료.pdf')


@pytest.mark.parametrize('payload,error',[
    ({},DownloadUnavailableError),({'fileYn':'Y'},SchemaError),
    ({'fileYn':'Y','pdfFile':'https://evil.example/x.pdf'},SchemaError),
    ({'fileYn':'Y','pdfFile':'/resource/publish/pdf/../secret.pdf'},SchemaError),
    ({'fileYn':'Y','pdfFile':'/resource/publish/pdf/%252e%252e/x.pdf'},SchemaError),
    ({'fileYn':'Y','pdfFile':'/resource/publish/pdf/a.pdf?bad'},SchemaError),
])
async def test_bad_preview_paths(browser,payload,error):
    prepare(browser,[related(),payload])
    async with VadaHubFileClient() as client:
        with pytest.raises(error):await client.get_document_preview(RESOURCE)


@pytest.mark.parametrize('change,error',[
    ({'serviceAuthCd':'PRIVATE'},AccessDeniedError),({'opnScopeSe':'MEMBER'},AccessDeniedError),
    ({'maskingYn':'Y'},AccessDeniedError),({'gridOpenYn':'N'},DownloadUnavailableError),
    ({'orginlTableNm':'CSV'},DownloadUnavailableError),({'relateDtaNm':'changed'},SchemaError),
])
async def test_preview_rechecks_public_resource(browser,change,error):
    prepare(browser,[related(ROW|change)])
    async with VadaHubFileClient() as client:
        with pytest.raises(error):await client.get_document_preview(RESOURCE)


async def test_table_snapshot_preserves_extra_columns_and_partial(browser):
    row=ROW|{'atrbSpceSe':'ATTRIBUTE','orginlTableNm':'table'}
    resource=_catalog.parse_resource(row,DATASET)
    payload={'resultOriginalOrder':['code'],'resultOrder':['코드'],'jsonArr':[{'code':'001','extra':'keep'}]}
    prepare(browser,[related(row),payload])
    async with VadaHubFileClient() as client:
        result=await client.get_table_preview(resource)
    assert result.partial and result.rows[0]['extra']=='keep' and result.rows[0]['code']=='001'
    assert browser.page.evaluate.await_args_list[1].args[1]['method']=='GET'
    with pytest.raises(TypeError):result.rows[0]['extra']='mutate'


@pytest.mark.parametrize('payload',[{}, {'resultOriginalOrder':['c'],'resultOrder':['C'],'jsonArr':[{}]},
    {'resultOriginalOrder':['c'],'resultOrder':['C'],'jsonArr':[{'c':[]}]},
    {'resultOriginalOrder':['c','c'],'resultOrder':['C','C'],'jsonArr':[]}])
async def test_bad_table_schema(browser,payload):
    row=ROW|{'atrbSpceSe':'ATTRIBUTE'}
    prepare(browser,[related(row),payload])
    async with VadaHubFileClient() as client:
        with pytest.raises(SchemaError):await client.get_table_preview(_catalog.parse_resource(row,DATASET))


async def test_library_download_wiring_and_store_roundtrip(browser,tmp_path,monkeypatch):
    prepare(browser,[related()])
    async with VadaHubFileClient() as client:
        helper=AsyncMock(return_value=('a'*64,(('safe.xlsx','b'*64),),10))
        monkeypatch.setattr(client,'_download_zip',helper)
        # 공개 버튼 동작 자체는 기존 download 상태기계/취소 테스트가 검증한다.
        button=SimpleNamespace(count=AsyncMock(return_value=1),first=SimpleNamespace(is_visible=AsyncMock(return_value=True)))
        original=browser.page.locator
        monkeypatch.setattr(browser.page,'locator',lambda selector:button if 'zipDown' in selector else original(selector))
        receipt=await client.download_library(RESOURCE,tmp_path/'download.zip')
        assert isinstance(receipt,LibraryArchiveReceipt) and helper.await_args.args[3] is None
    path=tmp_path/'source.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('folder/',b'');z.writestr('folder/table.xlsx',b'content')
    with pytest.raises(ArchiveError):inspect_archive(path,ArchiveLimits())
    checksum,members=inspect_archive(path,ArchiveLimits(),allow_directories=True)
    receipt=replace(receipt,sha256=checksum,member_sha256=members,byte_size=path.stat().st_size,local_path=path)
    store=LocalArchiveStore(tmp_path/'store')
    stored=await store.put(receipt)
    assert await store.put(receipt)==stored and await store.versions(RESOURCE)==(stored,)
    assert await store.recover()==() and stored.object_key.startswith('objects/library/documents/')
