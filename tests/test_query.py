"""공개 grid 페이지의 식별·schema·total·필터와 제한을 검증한다."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
import json
import pytest
from vadahub import (VadaHubClient, VadaHubFileClient, Dataset, DatasetLayer, LibraryResource, AsyncTokenBucket,
                     SchemaError, DownloadUnavailableError, AccessDeniedError)

DATASET=Dataset('5241','2022-10-19','파랑 예측','설명','https://vadahub.go.kr',catalog='api_analysis',api_id='142')
RESOURCE=LibraryResource(DATASET,'5248','예측','forecast_table','FORECAST_TABLE','ATTRIBUTE','OPEN','ALL',True,True,False,'5248')
SCHEMA={'tableInfo':[{'gid':1,'codeName':'001'}], 'schemaInfo':[
    {'attname':'code_name','description':'코드'},{'attname':'gid','description':'ID'}]}
PAGE={'draw':1,'setRecordsTotal':5,'recordsFiltered':2,'data':[{'gid':1,'codeName':'001'},{'gid':2,'codeName':'001'}]}


def wire(payload):return {'status':200,'text':json.dumps(payload)}


async def test_bounded_page_schema_join_and_request(browser,monkeypatch):
    browser.page.evaluate=AsyncMock(side_effect=[wire(SCHEMA),wire(PAGE)])
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        monkeypatch.setattr(client,'_current_resource',AsyncMock(return_value=RESOURCE))
        result=await client.query_table(RESOURCE,page_size=2,filters={'codeName':'001'},order_by='codeName',descending=False)
    assert result.rows[0]['codeName']=='001' and result.labels==('ID','코드')
    assert result.source_columns==('gid','code_name') and result.total==5 and result.filtered_total==2
    data=browser.page.evaluate.await_args_list[1].args[1]['data']
    assert data['order[0][column]']==1 and data['order[0][dir]']=='asc'
    assert data['columns[1][search][value]']=='001' and data['length']==2
    with pytest.raises(TypeError):result.rows[0]['gid']=3


@pytest.mark.parametrize('kwargs',[{'start':-1},{'start':True},{'start':1000001},{'page_size':0},{'page_size':201},
    {'descending':'true'},{'filters':[]},{'filters':{'x':'a'*129}},{'filters':{'x':'\n'}}])
async def test_invalid_query_no_browser(browser,kwargs):
    async with VadaHubClient() as client:
        with pytest.raises(ValueError): await client.query_table(RESOURCE,**kwargs)
    browser.manager.start.assert_not_awaited()


@pytest.mark.parametrize('payload,error',[
    ({'tableInfo':[],'schemaInfo':[]},DownloadUnavailableError),({},SchemaError),
    ({'tableInfo':'','schemaInfo':''},DownloadUnavailableError),
    (SCHEMA|{'schemaInfo':[{'attname':'wrong','description':'x'}]},SchemaError),
    (SCHEMA|{'schemaInfo':[{'attname':'code_name','description':'x'},{'attname':'codeName','description':'x'}]},SchemaError),
    (SCHEMA|{'tableInfo':[{'codeName':'001','codename':'002'}]},SchemaError),
])
async def test_bad_grid_schema(browser,monkeypatch,payload,error):
    browser.page.evaluate=AsyncMock(return_value=wire(payload))
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        monkeypatch.setattr(client,'_current_resource',AsyncMock(return_value=RESOURCE))
        with pytest.raises(error):await client.query_table(RESOURCE)


@pytest.mark.parametrize('change',[{'draw':True},{'draw':2},{'setRecordsTotal':None},{'recordsFiltered':6},
    {'data':[]},{'data':[{'gid':1}]},{'data':[{'gid':1,'codeName':float('nan')}]}])
async def test_bad_grid_page_not_partial_success(browser,monkeypatch,change):
    browser.page.evaluate=AsyncMock(side_effect=[wire(SCHEMA),wire(PAGE|change)])
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        monkeypatch.setattr(client,'_current_resource',AsyncMock(return_value=RESOURCE))
        with pytest.raises(SchemaError):await client.query_table(RESOURCE,page_size=2)


@pytest.mark.parametrize('kwargs',[{'filters':{'unknown':'1'}},{'order_by':'unknown'}])
async def test_unknown_columns_never_sent(browser,monkeypatch,kwargs):
    browser.page.evaluate=AsyncMock(return_value=wire(SCHEMA))
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        monkeypatch.setattr(client,'_current_resource',AsyncMock(return_value=RESOURCE))
        with pytest.raises(ValueError):await client.query_table(RESOURCE,**kwargs)
    assert browser.page.evaluate.await_count==1


async def test_api_resource_alias_preserves_catalog_meta(browser):
    async def goto(url,**kwargs):browser.page.url=url;return SimpleNamespace(status=200)
    browser.page.goto.side_effect=goto
    row=dict(metaSn=5248,histDe='2022-10-19',bsisDtaSn=5248,bsisDtaNm='예측',relateDtaNm='forecast_table',
        orginlTableNm=None,atrbSpceSe='ATTRIBUTE',serviceAuthCd='OPEN',opnScopeSe='ALL',gridOpenYn='Y',dwldPosblYn='Y',maskingYn='N')
    browser.page.evaluate=AsyncMock(side_effect=[wire({'resultList':[row],'resultListTotCnt':1}),wire({'resultList':[row],'resultListTotCnt':1})])
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        values=await client.list_resources(DATASET)
        assert values[0].dataset.dataset_id=='5241' and values[0].backing_dataset_id=='5248'
        assert await client.list_api_layers(DATASET)==()
    assert browser.page.evaluate.await_args_list[0].args[1]['data']['metaSn']=='5248'


@pytest.mark.parametrize('change',[{'serviceAuthCd':'PRIVATE'},{'opnScopeSe':'MEMBER'},{'maskingYn':'Y'}])
async def test_api_spatial_gate_at_discovery_and_download(browser,tmp_path,change):
    async def goto(url,**kwargs):browser.page.url=url;return SimpleNamespace(status=200)
    browser.page.goto.side_effect=goto
    row=dict(metaSn=5248,histDe='2022-10-19',bsisDtaSn=5248,bsisDtaNm='예측',relateDtaNm='forecast_table',
        orginlTableNm=None,atrbSpceSe='SPATIAL',serviceAuthCd='OPEN',opnScopeSe='ALL',gridOpenYn='Y',dwldPosblYn='Y',maskingYn='N')
    payload={'resultList':[row|change],'resultListTotCnt':1}
    browser.page.evaluate=AsyncMock(side_effect=[wire(payload),wire(payload)])
    layer=DatasetLayer('5248','2022-10-19','5248','forecast_table','예측','OPEN','ALL',True,True,False,True)
    async with VadaHubFileClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        assert await client.list_api_layers(DATASET)==()
        with pytest.raises(AccessDeniedError):await client.download(layer,tmp_path/'blocked.zip')
    assert not (tmp_path/'blocked.zip').exists()


async def test_real_unknown_permission_values_are_preserved(browser):
    async def goto(url,**kwargs):browser.page.url=url;return SimpleNamespace(status=200)
    browser.page.goto.side_effect=goto
    dataset=replace(DATASET,dataset_id='10077',api_id='147',catalog='api_original')
    row=dict(metaSn=10077,histDe='2022-10-19',bsisDtaSn=520798,bsisDtaNm='목록공개',relateDtaNm='public_table',
        orginlTableNm=None,atrbSpceSe='SPATIAL',serviceAuthCd='LIST_OPEN',opnScopeSe='ALL',gridOpenYn='N',dwldPosblYn=' ',maskingYn=' ')
    browser.page.evaluate=AsyncMock(side_effect=[wire({'resultList':[row],'resultListTotCnt':1})]*2)
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        resource=(await client.list_resources(dataset))[0]
        assert resource.masked is None and resource.download_available is None
        assert dict(resource.raw_availability)['dwldPosblYn']==' '
        with pytest.raises(AccessDeniedError):await client.query_table(resource)
