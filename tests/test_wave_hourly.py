"""시각별 파랑의 고정 질의·공개 상태·두 원천 결합·실패 경계를 검증한다."""
import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
import json
from unittest.mock import AsyncMock
import pytest
from vadahub import (VadaHubClient, AsyncTokenBucket, SchemaError, AccessDeniedError,
                     NetworkError, RateLimitError)
from vadahub.wave_hourly import TYPES, _feature, _xml
from test_wave import DATASET, RESOURCE, DAY, GRID, setup as base_setup, wire

CAP = '<WFS_Capabilities xmlns="http://www.opengis.net/wfs" version="1.1.0"><FeatureTypeList>' + ''.join(
    f'<FeatureType><Name>{name}</Name><DefaultSRS>urn:x-ogc:def:crs:EPSG:5179</DefaultSRS></FeatureType>'
    for name in TYPES) + '</FeatureTypeList></WFS_Capabilities>'


def schema(field):
    return '<schema xmlns="http://www.w3.org/2001/XMLSchema"><complexType><sequence>' + ''.join(
        f'<element name="{name}"/>' for name in ('grid_cd', 'geom', 'anals_ymd', 'anals_hhs', 'wvdrct', field)) + '</sequence></complexType></schema>'


def collection(index=0):
    return {'type': 'FeatureCollection', 'totalFeatures': 1, 'crs': {'type': 'name', 'properties': {
        'name': 'urn:ogc:def:crs:EPSG::5179'}}, 'features': [{'type': 'Feature', 'id': TYPES[index].split(':')[1] + '.fid-123',
        'geometry_name': 'geom', 'geometry': {'type': 'MultiPolygon', 'coordinates': [[[[1, 2], [3, 4], [5, 6], [1, 2]]]]},
        'properties': {'grid_cd': GRID, 'anals_ymd': '20180610', 'anals_hhs': '18', 'wvdrct': 132.001,
                       ('wvhgh' if index == 0 else 'avg_wv_pd'): (1.351 if index == 0 else 12.2)}}]}


def setup(monkeypatch, client, browser, *, cap=CAP, height=None, period=None):
    base_setup(monkeypatch, client, browser)
    responses = [{'status': 200, 'text': text} for text in (cap, schema('wvhgh'), schema('avg_wv_pd'))]
    responses += [wire(height if height is not None else collection()), wire(period if period is not None else collection(1))]
    browser.page.evaluate = AsyncMock(side_effect=responses)


async def test_actual_values_provenance_fixed_requests_and_immutable(browser, monkeypatch):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        result = await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
        row, = result.rows
        assert (row.wave_height, row.wave_direction, row.mean_wave_period) == (1.351, 132.001, 12.2)
        assert result.resource == RESOURCE and result.type_names == TYPES and result.collected_at.tzinfo
        assert json.loads(row.height_feature_json) == collection()['features'][0]
        assert json.loads(row.period_feature_json) == collection(1)['features'][0]
        assert row.height_fid != row.period_fid
        with pytest.raises(TypeError): row.height_attributes['wvhgh'] = 3
        calls = browser.page.evaluate.await_args_list
        assert len(calls) == 5
        for index, call in enumerate(calls[-2:]):
            args = call.args[1]
            assert args['path'] == '/imap/proxyRun.do' and args['method'] == 'GET'
            assert args['data']['typeName'] == TYPES[index]
            assert args['data']['viewparams'] == 'anals_ymd:20180610;anals_hhs:18'
            assert args['data']['cql_filter'] == "grid_cd='GR3_F4J12_H'" and args['data']['maxFeatures'] == '2'


@pytest.mark.parametrize('change', [{'grid_code': 'GR3_X;DROP'}, {'grid_code': 'GR3_한글'}, {'grid_code': 3},
    {'analysis_date': datetime(2018, 6, 10)}, {'analysis_date': '20180610'}, {'hour': True}, {'hour': 24},
    {'hour': -3}, {'hour': 2}, {'hour': 18.0}])
async def test_invalid_input_no_browser(browser, change):
    async with VadaHubClient() as client:
        with pytest.raises(ValueError):
            await client.get_wave3min_hourly(**({'grid_code': GRID, 'analysis_date': DAY, 'hour': 18} | change))
    browser.manager.start.assert_not_awaited()


@pytest.mark.parametrize('change,error', [({'source_name': 'other'}, SchemaError),
    ({'attribute_kind': 'DOCUMENT'}, SchemaError), ({'grid_available': False}, SchemaError),
    ({'service_auth': 'MEMBER'}, AccessDeniedError), ({'open_scope': 'PART'}, AccessDeniedError),
    ({'masked': True}, AccessDeniedError)])
async def test_fresh_access_not_bypassed(browser, monkeypatch, change, error):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        client._current_resource.return_value = replace(RESOURCE, **change)
        with pytest.raises(error): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
        browser.page.evaluate.assert_not_awaited()


async def test_discovery_missing_and_duplicates(browser, monkeypatch):
    async with VadaHubClient() as client:
        setup(monkeypatch, client, browser)
        for datasets, resources in [((), (RESOURCE,)), ((DATASET, DATASET), (RESOURCE,)), ((DATASET,), ())]:
            client.list_datasets.return_value, client.list_resources.return_value = datasets, resources
            with pytest.raises(SchemaError): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
        browser.page.evaluate.assert_not_awaited()


@pytest.mark.parametrize('cap', [CAP.replace('1.1.0', '2.0.0'), CAP.replace(TYPES[0], 'other'),
    CAP.replace('EPSG:5179', 'EPSG:4326'), CAP.replace('</FeatureTypeList>', CAP[CAP.index('<FeatureType>'):CAP.index('</FeatureType>')+14] + '</FeatureTypeList>')])
async def test_wrong_capabilities(browser, monkeypatch, cap):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser, cap=cap)
        with pytest.raises(SchemaError): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)


@pytest.mark.parametrize('body,error', [('<html/>', AccessDeniedError), ('<ExceptionReport/>', AccessDeniedError),
    ('<broken', SchemaError), ('<!DOCTYPE schema [<!ENTITY x "y">]><schema/>', SchemaError)])
def test_no_xml_entities_or_error_success(body, error):
    with pytest.raises(error): _xml(body)


@pytest.mark.parametrize('value', [{}, {'status': True}, {'status': 200, 'too_large': True},
    {'status': 200}, {'status': 200, 'text': '가' * 700000}])
async def test_bad_transport(browser, monkeypatch, value):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        browser.page.evaluate.side_effect = None
        browser.page.evaluate.return_value = value
        with pytest.raises(SchemaError): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)


@pytest.mark.parametrize('status,error', [(401, AccessDeniedError), (403, AccessDeniedError),
    (302, AccessDeniedError), (429, RateLimitError), (503, NetworkError)])
async def test_status_no_retry(browser, monkeypatch, status, error):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        browser.page.evaluate.side_effect = None
        browser.page.evaluate.return_value = {'status': status}
        with pytest.raises(error): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
        assert browser.page.evaluate.await_count == 1


@pytest.mark.parametrize('body', ['{}', '[]', '{', '<ExceptionReport/>', '{"a":1,"a":2}',
    '[' * 2000, json.dumps(collection()).replace('1.351', 'NaN'),
    json.dumps(collection()).replace('1.351', '1e999')])
def test_invalid_feature_json(body):
    with pytest.raises((SchemaError, AccessDeniedError)): _feature(body, 0, GRID, '20180610', '18')


@pytest.mark.parametrize('change', ['count_bool', 'count_two', 'wrong_grid', 'wrong_date', 'wrong_hour',
    'bool_value', 'string_value', 'huge_value', 'no_field', 'wrong_fid', 'wrong_crs', 'wrong_geom', 'empty_coords',
    'nonfinite_coords', 'depth_coords', 'empty_properties', 'extra_field', 'not_feature'])
def test_invalid_row_identity_and_shapes(change):
    payload = collection(); feature = payload['features'][0]; props = feature['properties']
    if change == 'count_bool': payload['totalFeatures'] = True
    if change == 'count_two': payload['totalFeatures'] = 2
    if change == 'wrong_grid': props['grid_cd'] = 'GR3_OTHER'
    if change == 'wrong_date': props['anals_ymd'] = '20180609'
    if change == 'wrong_hour': props['anals_hhs'] = '21'
    if change == 'bool_value': props['wvhgh'] = True
    if change == 'string_value': props['wvhgh'] = '1.351'
    if change == 'huge_value': props['wvhgh'] = 10**400
    if change == 'no_field': del props['wvdrct']
    if change == 'wrong_fid': feature['id'] = 'opn.16301943'
    if change == 'wrong_crs': payload['crs'] = None
    if change == 'wrong_geom': feature['geometry'] = None
    if change == 'empty_coords': feature['geometry']['coordinates'] = []
    if change == 'nonfinite_coords': feature['geometry']['coordinates'] = [[True]]
    if change == 'depth_coords': feature['geometry']['coordinates'] = [[[[[[[[[1]]]]]]]]]
    if change == 'empty_properties': feature['properties'] = None
    if change == 'extra_field': props['gid'] = 1
    if change == 'not_feature': payload['features'][0] = []
    with pytest.raises(SchemaError): _feature(json.dumps(payload), 0, GRID, '20180610', '18')


@pytest.mark.parametrize('case', ['both_empty', 'one_empty', 'direction_mismatch', 'geom_mismatch', 'nulls'])
async def test_pair_join_boundaries(browser, monkeypatch, case):
    a, b = collection(), collection(1)
    empty = {'type': 'FeatureCollection', 'totalFeatures': 0, 'features': []}
    if case in ('both_empty', 'one_empty'): a = deepcopy(empty)
    if case == 'both_empty': b = deepcopy(empty)
    if case == 'direction_mismatch': b['features'][0]['properties']['wvdrct'] = 0
    if case == 'geom_mismatch': b['features'][0]['geometry']['coordinates'][0][0][0][0] = 7
    if case == 'nulls':
        for obj, field in [(a, 'wvhgh'), (b, 'avg_wv_pd')]:
            obj['features'][0]['properties'][field] = None
            obj['features'][0]['properties']['wvdrct'] = None
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser, height=a, period=b)
        if case in ('one_empty', 'direction_mismatch', 'geom_mismatch'):
            with pytest.raises(SchemaError): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
        else:
            result = await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
            assert len(result.rows) == (0 if case == 'both_empty' else 1)
            if result.rows: assert result.rows[0].wave_height is None and result.rows[0].mean_wave_period is None


async def test_timeout_and_cancellation_cover_discovery_and_cleanup(browser, monkeypatch):
    async def wait(*args, **kwargs): await asyncio.Event().wait()
    async with VadaHubClient(timeout=0.02) as client:
        monkeypatch.setattr(client, 'list_datasets', wait)
        with pytest.raises(NetworkError, match='전체 작업'): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        started = asyncio.Event()
        async def blocked(*args, **kwargs):
            started.set(); await asyncio.Event().wait()
        browser.page.evaluate = blocked
        task = asyncio.create_task(client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18))
        await started.wait(); task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    browser.context.close.assert_awaited_once()


@pytest.mark.parametrize('coords', [[1, 2], [[[[1]]]], [[[[1, 2], [3, 4], [1, 2]]]],
    [[[[1, 2], [3, 4], [5, 6], [7, 8]]]], [None], [[None]],
    [[[[1, 2, 3], [3, 4], [5, 6], [1, 2]]]], [[[[1, 2], [3, True], [5, 6], [1, 2]]]]])
def test_malformed_multipolygon_never_becomes_success(coords):
    payload = collection()
    payload['features'][0]['geometry']['coordinates'] = coords
    with pytest.raises(SchemaError): _feature(json.dumps(payload), 0, GRID, '20180610', '18')


async def test_same_broken_geometry_on_both_views_is_rejected(browser, monkeypatch):
    a, b = collection(), collection(1)
    for payload in (a, b): payload['features'][0]['geometry']['coordinates'] = [1, 2]
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser, height=a, period=b)
        with pytest.raises(SchemaError): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)


async def test_changed_schema_and_unbounded_capabilities(browser, monkeypatch):
    async with VadaHubClient(rate_limiter=AsyncTokenBucket(100000)) as client:
        setup(monkeypatch, client, browser)
        browser.page.evaluate.side_effect = [{'status': 200, 'text': CAP}, {'status': 200, 'text': schema('other')}]
        with pytest.raises(SchemaError): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
        browser.page.evaluate.side_effect = None
        browser.page.evaluate.return_value = {'status': 200, 'text': '<WFS_Capabilities xmlns="http://www.opengis.net/wfs" version="1.1.0"><FeatureTypeList>' + '<FeatureType/>' * 5001 + '</FeatureTypeList></WFS_Capabilities>'}
        with pytest.raises(SchemaError): await client.get_wave3min_hourly(GRID, analysis_date=DAY, hour=18)
