"""관광자료의 시점·정체성·결측과 async facade 경계를 검증한다."""
from contextlib import aclosing
from dataclasses import replace
from datetime import date
from types import MappingProxyType
from unittest.mock import AsyncMock
import pytest
from vadahub import (TOURISM_SOURCES, Dataset, DatasetLayer, SpatialFeature, VadaHubFileClient,
    TourismLayer, SchemaError, tourism_source, tourism_from_feature, search_tourism)


def feature(category='experience_village', **changes):
    source = tourism_source(category)
    keys = (source.name_field, source.address_field, source.phone_field, source.website_field,
        source.region_code_field, source.year_field, source.date_field, *source.region_fields, *source.detail_fields)
    attrs = dict.fromkeys((key for key in keys if key), None)
    attrs.update(changes)
    layer = DatasetLayer(source.dataset_id, '2026-01-01', source.layer_id, source.table_name,
        source.title, 'OPEN', 'ALL', True, True)
    return SpatialFeature(layer, '001', 'gid', MappingProxyType({'c1': '001'}), MappingProxyType(attrs),
        b'raw', 'POINT', None, None, None, 'a'*64, geometry_valid=True)


@pytest.mark.parametrize('source', TOURISM_SOURCES)
def test_each_source_missing_values_keep_provenance(source):
    row = feature(source.category)
    place = tourism_from_feature(row, category=source.category)
    assert place.feature is row and place.name is None and place.website is None
    assert place.key == (source.dataset_id, '2026-01-01', source.layer_id, '001', 'a'*64)
    assert place.survey_year is None and place.source_date is None


def test_dates_contact_and_search_semantics():
    row = feature(vlg_nm=' 갈남 마을 ', sido_nm='강원도', sgg_nm='삼척시', loc_adrs='강원도 삼척시',
        ceonm='원문에만', ceophno='01000000000', data_std='2023-04-24', homepage='http://갈남.kr',
        prgr_nm1='카누+체험', created_date='2024/01/23')
    place = tourism_from_feature(row, category='experience_village')
    assert place.name == '갈남 마을' and place.region == '강원도 삼척시'
    assert place.phone is None and place.source_date == date(2023, 4, 24)
    assert place.source.date_meaning == '자료기준일' and place.survey_year is None
    assert list(search_tourism([place], name_contains='갈남', region_contains=' 삼척 ')) == [place]
    assert list(search_tourism([place], name_contains='없는')) == []
    assert list(search_tourism([place], region_contains='제주')) == []
    legacy = tourism_from_feature(feature('experience_village_legacy', invs_yr='2014', fvex_vllg_tno='032001'), category='experience_village_legacy')
    assert legacy.survey_year == 2014 and legacy.phone == '032001' and legacy.key != place.key
    fishing = tourism_from_feature(feature('sea_fishing', mfgg_ymd=date(2016, 12, 4),
        rel_dept_tno='0442005539', fcl_lnm_addr='제주'), category='sea_fishing')
    assert fishing.phone is None and fishing.source.date_meaning == '제작일'
    assert list(search_tourism([fishing], region_contains='제주')) == [fishing]
    assert list(search_tourism([fishing], name_contains='낚시')) == []


@pytest.mark.parametrize('url', ['javascript:alert(1)', '//example.org', 'http://user:pw@host',
    'https://host:bad', 'https://host/\nhi', 'http://host\\evil', 'http://['])
def test_unusable_homepage_keeps_only_raw(url):
    row = feature(homepage=url)
    assert tourism_from_feature(row, category='experience_village').website is None
    assert row.attributes['homepage'] == url


@pytest.mark.parametrize('attrs', [{'data_std': '2023-02-30'}, {'data_std': 2023}, {'vlg_nm': 123},
    {'data_std': '20230424'}])
def test_schema_errors_are_not_empty_results(attrs):
    with pytest.raises(SchemaError): tourism_from_feature(feature(**attrs), category='experience_village')
    with pytest.raises(ValueError): tourism_source('숙박')


def test_layer_identity_schema_and_year_guards():
    row = feature('observatory', invs_yr='2014')
    with pytest.raises(SchemaError): tourism_from_feature(replace(row, layer=replace(row.layer, dataset_id='other')), category='observatory')
    with pytest.raises(SchemaError): tourism_from_feature(replace(row, attributes={}), category='observatory')
    with pytest.raises(SchemaError): tourism_from_feature(feature('observatory', invs_yr='unknown'), category='observatory')


async def test_catalog_current_history_and_identity_guards(monkeypatch):
    row = feature('beach')
    dataset = Dataset(row.layer.dataset_id, row.layer.history_date, '해수욕장', '', 'https://example.org')
    async with VadaHubFileClient() as client:
        monkeypatch.setattr(client, 'list_datasets', AsyncMock(return_value=(dataset,)))
        monkeypatch.setattr(client, 'list_layers', AsyncMock(return_value=(row.layer,)))
        selected = await client.list_tourism_layers('beach')
        assert selected == (TourismLayer(tourism_source('beach'), row.layer),)
        assert selected[0].layer.history_date == '2026-01-01'
        client.list_layers.return_value = (replace(row.layer, table_name='wrong'),)
        with pytest.raises(SchemaError): await client.list_tourism_layers('beach')
        client.list_datasets.return_value = ()
        with pytest.raises(SchemaError): await client.list_tourism_layers('beach')
        client.list_datasets.return_value = (dataset, dataset)
        with pytest.raises(SchemaError): await client.list_tourism_layers('beach')


async def test_async_stream_cleanup_and_option_forwarding(monkeypatch):
    row = feature('beach', beach_name='이금포')
    closed = []
    options = []
    async def stream(layer, **kwargs):
        options.append(kwargs)
        try:
            yield row
            yield row
        finally:
            closed.append(True)
    async with VadaHubFileClient() as client:
        monkeypatch.setattr(client, 'list_tourism_layers', AsyncMock(return_value=(TourismLayer(tourism_source('beach'), row.layer),)))
        monkeypatch.setattr(client, 'iter', stream)
        async with aclosing(client.iter_tourism('beach', batch_size=1, invalid_geometry='preserve')) as items:
            async for item in items:
                assert item.name == '이금포'
                break
        assert closed == [True] and options[0]['invalid_geometry'] == 'preserve' and options[0]['batch_size'] == 1
        assert len(await client.load_tourism('beach')) == 2
        assert options[1]['invalid_geometry'] == 'raise' and closed == [True, True]
