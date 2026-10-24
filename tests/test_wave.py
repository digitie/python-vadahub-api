"""파랑 날짜별 통계의 질의 경계·출처·정책·실패를 검증한다."""
import asyncio
from dataclasses import replace
from datetime import date, datetime
import json
from unittest.mock import AsyncMock
import pytest
from vadahub import (VadaHubClient, Dataset, LibraryResource, AsyncTokenBucket,
    SchemaError, AccessDeniedError, RateLimitError, NetworkError)

DATASET = Dataset('5243', '2022-10-19', '파랑3분', '', 'https://vadahub.go.kr', catalog='api_original', api_id='139')
RESOURCE = LibraryResource(DATASET, '520360', '파랑3분', 'opn_tb_grid_cont_wv_3min', 'SPATIAL',
    'SPATIAL', 'OPEN', 'ALL', True, True, False, '5243')
DAY = date(2018, 6, 10)
GRID = 'GR3_F4J12_H'
ROW = {'gridCd': GRID, 'analsYmd': '20180610', 'wvhgh': 1.6}


def wire(payload):
    return {'status': 200, 'text': json.dumps(payload)}


def setup(monkeypatch, client, browser, payload=None):
    monkeypatch.setattr(client, 'list_datasets', AsyncMock(return_value=(DATASET,)))
    monkeypatch.setattr(client, 'list_resources', AsyncMock(return_value=(RESOURCE,)))
    monkeypatch.setattr(client, '_current_resource', AsyncMock(return_value=RESOURCE))
    navigate = AsyncMock()
    monkeypatch.setattr('vadahub.client._open_page', navigate)
    browser.page.evaluate = AsyncMock(return_value=wire(payload if payload is not None else {'layerStatsWv': [ROW]}))
    return navigate


async def test_source_scope_params_and_immutable_values(browser, monkeypatch):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        navigate = setup(monkeypatch, client, browser)
        result = await client.get_wave3min_statistics(GRID, start_date=DAY, end_date=DAY)
        assert result.resource == RESOURCE and result.rows[0].analysis_date == DAY and result.rows[0].value == 1.6
        assert result.measure == 'height' and result.collected_at.tzinfo is not None
        assert result.rows[0].raw_attributes == ROW
        with pytest.raises(TypeError): result.rows[0].raw_attributes['wvhgh'] = 2
        args = browser.page.evaluate.await_args.args[1]
        assert args['path'] == '/user/aiModel/selectGridStatsPastWv.do'
        assert args['data'] == {'gridNo': GRID, 'ogType': 'grid_3_step_a', 'type': 'wvhgh',
            'startDate': '20180610', 'endDate': '20180610', 'tableNm': 'WV_3MIN'}
        assert navigate.await_args.args[1:] == (result.source_url, '.cont-wrapper')


@pytest.mark.parametrize('rows', [[], [{'gridCd': GRID, 'analsYmd': '20180610', 'pd': None}]])
async def test_period_empty_or_missing_value(browser, monkeypatch, rows):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser, {'layerStatsWv': rows})
        result = await client.get_wave3min_statistics(GRID, start_date=DAY, end_date=date(2018, 6, 16), measure='period')
        assert len(result.rows) == len(rows) and all(row.value is None for row in result.rows)
        assert result.measure == 'period' and browser.page.evaluate.await_args.args[1]['data']['type'] == 'pd'


@pytest.mark.parametrize('change', [{'grid_code': 'GR3_x'}, {'grid_code': 'GR3_A;DROP'}, {'grid_code': 123},
    {'start_date': '20180610'}, {'start_date': datetime(2018, 6, 10)}, {'end_date': date(2018, 6, 9)},
    {'end_date': date(2018, 6, 17)}, {'measure': 'raw'}, {'measure': True}])
async def test_bad_query_never_starts_browser(browser, change):
    kwargs = {'grid_code': GRID, 'start_date': DAY, 'end_date': DAY} | change
    async with VadaHubClient() as client:
        with pytest.raises(ValueError): await client.get_wave3min_statistics(**kwargs)
    browser.manager.start.assert_not_awaited()


@pytest.mark.parametrize('payload', [{}, {'layerStatsWv': None}, {'layerStatsWv': [ROW, ROW]},
    {'layerStatsWv': [ROW | {'gridCd': 'GR3_OTHER'}]}, {'layerStatsWv': [ROW | {'analsYmd': '20180230'}]},
    {'layerStatsWv': [ROW | {'analsYmd': '2018-06-10'}]}, {'layerStatsWv': [ROW | {'analsYmd': '20180609'}]},
    {'layerStatsWv': [ROW | {'wvhgh': True}]}, {'layerStatsWv': [ROW | {'wvhgh': '1.6'}]},
    {'layerStatsWv': [ROW | {'wvhgh': 10**400}]}, {'layerStatsWv': [ROW | {'wvhgh': float('inf')}]},
    {'layerStatsWv': [ROW | {'extra': {}}]}, {'layerStatsWv': [{'gridCd': GRID, 'analsYmd': '20180610'}]}])
async def test_bad_source_is_not_empty_success(browser, monkeypatch, payload):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser, payload)
        with pytest.raises(SchemaError): await client.get_wave3min_statistics(GRID, start_date=DAY, end_date=DAY)


async def test_duplicate_dates_in_multiple_day_range(browser, monkeypatch):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser, {'layerStatsWv': [ROW, ROW]})
        with pytest.raises(SchemaError, match='중복'):
            await client.get_wave3min_statistics(GRID, start_date=DAY, end_date=date(2018, 6, 11))


@pytest.mark.parametrize('change,error', [({'source_name': 'other'}, SchemaError),
    ({'attribute_kind': 'DOCUMENT'}, SchemaError), ({'grid_available': False}, SchemaError),
    ({'service_auth': 'PARTIAL'}, AccessDeniedError), ({'masked': None}, AccessDeniedError)])
async def test_fresh_source_state_guards(browser, monkeypatch, change, error):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        client._current_resource.return_value = replace(RESOURCE, **change)
        with pytest.raises(error): await client.get_wave3min_statistics(GRID, start_date=DAY, end_date=DAY)
        browser.page.evaluate.assert_not_awaited()


async def test_missing_or_duplicated_service_and_resource(browser, monkeypatch):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        for datasets, resources in [((), (RESOURCE,)), ((DATASET, DATASET), (RESOURCE,)), ((DATASET,), ())]:
            client.list_datasets.return_value = datasets
            client.list_resources.return_value = resources
            with pytest.raises(SchemaError): await client.get_wave3min_statistics(GRID, start_date=DAY, end_date=DAY)
        browser.page.evaluate.assert_not_awaited()


async def test_rate_limit_no_fallback(browser, monkeypatch):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        browser.page.evaluate.return_value = {'status': 429, 'text': ''}
        with pytest.raises(RateLimitError): await client.get_wave3min_statistics(GRID, start_date=DAY, end_date=DAY)
        assert browser.page.evaluate.await_count == 1


async def test_cancel_releases_owned_context(browser, monkeypatch):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        started = asyncio.Event()
        async def wait(*args, **kwargs):
            started.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(client, '_post', wait)
        task = asyncio.create_task(client.get_wave3min_statistics(GRID, start_date=DAY, end_date=DAY))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    browser.context.close.assert_awaited_once()


async def test_timeout_includes_catalog_discovery(browser, monkeypatch):
    async def wait(*args, **kwargs):
        await asyncio.Event().wait()
    async with VadaHubClient(timeout=0.02) as client:
        monkeypatch.setattr(client, 'list_datasets', wait)
        with pytest.raises(NetworkError, match='전체 작업'):
            await client.get_wave3min_statistics(GRID, start_date=DAY, end_date=DAY)
    browser.manager.start.assert_not_awaited()
