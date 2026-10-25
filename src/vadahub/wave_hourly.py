"""공개 WFS의 고정된 두 파랑 뷰를 시각·격자로 한정 조회한다."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from .exceptions import AccessDeniedError, SchemaError
from .models import WaveHourlyRecord, WaveHourlySnapshot
from .wave import SOURCE_URL

if TYPE_CHECKING:
    from playwright.async_api import Page
    from .client import VadaHubClient

PROXY = '/imap/proxyRun.do'
TYPES = ('ofbd-DB:tb_grid_cont_wv_wvhgh_3min', 'ofbd-DB:tb_grid_cont_wv_pd_3min')
_WFS = '{http://www.opengis.net/wfs}'
_XSD = '{http://www.w3.org/2001/XMLSchema}'
_FIELDS = ({'grid_cd', 'anals_ymd', 'anals_hhs', 'wvdrct', 'wvhgh'},
           {'grid_cd', 'anals_ymd', 'anals_hhs', 'wvdrct', 'avg_wv_pd'})


async def _request(client: VadaHubClient, page: Page, params: dict[str, str]) -> str:
    """기존 제한·same-origin 전송·2MiB 경계를 유지하며 XML도 원문으로 받는다."""
    from .client import _POST, _check_status
    await client.rate_limiter.acquire()
    result = await page.evaluate(_POST, {'path': PROXY, 'data': params, 'method': 'GET'})
    if not isinstance(result, dict) or type(result.get('status')) is not int:
        raise SchemaError('WFS HTTP 응답 형식 오류')
    _check_status(result['status'])
    body = result.get('text')
    if result.get('too_large') or not isinstance(body, str) or len(body.encode('utf-8')) > 2097152:
        raise SchemaError('WFS 원문 누락 또는 2MiB 상한 초과')
    return body


def _xml(body: str) -> ET.Element:
    """DTD/entity를 거부하고 schemaLocation 등 외부 URL을 읽지 않는다."""
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)', body, re.I):
        raise SchemaError('WFS XML DTD/entity 금지')
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise SchemaError('잘못된 WFS XML') from exc
    if root.tag not in (_WFS + 'WFS_Capabilities', _XSD + 'schema'):
        raise AccessDeniedError('WFS 메타데이터 대신 오류/접근 화면입니다')
    return root


async def _metadata(client: VadaHubClient, page: Page) -> None:
    common = {'service': 'WFS', 'version': '1.1.0'}
    root = _xml(await _request(client, page, common | {'request': 'GetCapabilities'}))
    if root.tag != _WFS + 'WFS_Capabilities' or root.get('version') != '1.1.0':
        raise SchemaError('WFS capabilities 버전 오류')
    types = root.findall('./' + _WFS + 'FeatureTypeList/' + _WFS + 'FeatureType')
    if len(types) > 5000:
        raise SchemaError('WFS 공개 타입 수 상한 초과')
    for index, name in enumerate(TYPES):
        matches = [node for node in types if node.findtext(_WFS + 'Name') == name]
        if len(matches) != 1 or matches[0].findtext(_WFS + 'DefaultSRS') != 'urn:x-ogc:def:crs:EPSG:5179':
            raise SchemaError('WFS 고정 파랑 타입/CRS 등록 오류')
        schema = _xml(await _request(client, page, common | {'request': 'DescribeFeatureType', 'typeName': name}))
        fields = schema.findall('.//' + _XSD + 'sequence/' + _XSD + 'element')
        if (schema.tag != _XSD + 'schema' or len(fields) != len(_FIELDS[index]) + 1
                or {n.get('name') for n in fields} != _FIELDS[index] | {'geom'}):
            raise SchemaError('WFS 파랑 필드 schema가 바뀌었습니다')


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('중복 JSON key')
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError('JSON 비유한 상수 금지')


def _float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('JSON 비유한 실수 금지')
    return result


def _finite(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _geometry(value: Any, depth: int = 0) -> None:
    """좌표변환 없이 제한된 JSON 좌표의 형식·유한성만 검증한다."""
    if depth > 5 or not isinstance(value, list) or not value or len(value) > 10000:
        raise SchemaError('WFS geometry 좌표 구조 오류')
    for item in value:
        if isinstance(item, list):
            _geometry(item, depth + 1)
        elif not _finite(item):
            raise SchemaError('WFS geometry 비유한 좌표')


def _feature(body: str, index: int, grid: str, day: str, hour: str) -> dict | None:
    if body.lstrip().startswith('<'):
        raise AccessDeniedError('WFS JSON 대신 HTML/XML 오류입니다')
    try:
        payload = json.loads(body, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    except (ValueError, RecursionError) as exc:
        raise SchemaError('WFS JSON 형식/중복/depth 오류') from exc
    if (not isinstance(payload, dict) or payload.get('type') != 'FeatureCollection'
            or type(payload.get('totalFeatures')) is not int or payload['totalFeatures'] not in (0, 1)
            or not isinstance(payload.get('features'), list)
            or len(payload['features']) != payload['totalFeatures']):
        raise SchemaError('WFS 단일 시각 결과 count/목록 오류')
    if not payload['features']:
        return None
    if payload.get('crs') != {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::5179'}}:
        raise SchemaError('WFS 결과 CRS 오류')
    feature = payload['features'][0]
    if (not isinstance(feature, dict) or feature.get('type') != 'Feature'
            or not isinstance(feature.get('id'), str) or not feature['id'].startswith(TYPES[index].split(':')[1] + '.')
            or len(feature['id']) > 256 or feature.get('geometry_name') != 'geom'
            or not isinstance(feature.get('properties'), dict) or set(feature['properties']) != _FIELDS[index]):
        raise SchemaError('WFS feature/FID/속성 계약 오류')
    props = feature['properties']
    if (props['grid_cd'] != grid or props['anals_ymd'] != day or props['anals_hhs'] != hour
            or any(value is not None and not _finite(value) for key, value in props.items()
                   if key not in ('grid_cd', 'anals_ymd', 'anals_hhs'))):
        raise SchemaError('WFS 요청 identity 또는 측정값 오류')
    geom = feature.get('geometry')
    if not isinstance(geom, dict) or set(geom) != {'type', 'coordinates'} or geom['type'] != 'MultiPolygon':
        raise SchemaError('WFS geometry 타입 오류')
    _geometry(geom['coordinates'])
    return feature


async def get_wave3min_hourly(client: VadaHubClient, grid_code: str, *, analysis_date: date,
                               hour: int) -> WaveHourlySnapshot:
    """두 뷰의 동일 시각/격자/geometry/파향을 검증해 실제 값만 결합한다."""
    if (not isinstance(grid_code, str) or not re.fullmatch(r'GR3_[A-Z0-9_]{1,32}', grid_code)
            or type(analysis_date) is not date or type(hour) is not int or hour not in range(0, 24, 3)):
        raise ValueError('GR3 격자1개, date1개, 0..21의3시간 간격 정수 시각이 필요합니다')
    datasets = [d for d in await client.list_datasets(catalog='api_original') if d.api_id == '139']
    if len(datasets) != 1:
        raise SchemaError('API139 공개 안내가 없거나 중복입니다')
    resources = [r for r in await client.list_resources(datasets[0]) if r.resource_id == '520360']
    if len(resources) != 1:
        raise SchemaError('API139 연결자료 identity가 바뀌었습니다')
    async with client._browser.operation() as page:
        from .client import _open_page
        resource = await client._current_resource(page, resources[0])
        if (resource.source_name != 'opn_tb_grid_cont_wv_3min' or resource.dataset.api_id != '139'
                or resource.attribute_kind != 'SPATIAL' or not resource.grid_available):
            raise SchemaError('파랑3분 원천 계약이 바뀌었습니다')
        if resource.service_auth != 'OPEN' or resource.open_scope != 'ALL' or resource.masked is not False:
            raise AccessDeniedError('공개/전체/비마스킹 파랑 원천이 필요합니다')
        await _open_page(page, SOURCE_URL, '.cont-wrapper')
        await _metadata(client, page)
        day, hh = analysis_date.isoformat().replace('-', ''), f'{hour:02d}'
        features = []
        for index, name in enumerate(TYPES):
            body = await _request(client, page, {'service': 'WFS', 'version': '1.1.0',
                'request': 'GetFeature', 'typeName': name, 'outputFormat': 'application/json',
                'srsName': 'EPSG:5179', 'maxFeatures': '2', 'viewparams': f'anals_ymd:{day};anals_hhs:{hh}',
                'cql_filter': f"grid_cd='{grid_code}'"})
            features.append(_feature(body, index, grid_code, day, hh))
        height, period = features
        rows: tuple[WaveHourlyRecord, ...] = ()
        if (height is None) != (period is None):
            raise SchemaError('파랑 두 뷰 중 한쪽 시각만 있습니다')
        if height is not None and period is not None:
            a, b = height['properties'], period['properties']
            if height['geometry'] != period['geometry'] or a['wvdrct'] != b['wvdrct']:
                raise SchemaError('파랑 두 뷰의 geometry/파향이 다릅니다')
            rows = (WaveHourlyRecord(grid_code, analysis_date, hour, a['wvhgh'], a['wvdrct'], b['avg_wv_pd'],
                height['id'], period['id'], MappingProxyType(a), MappingProxyType(b),
                json.dumps(height, ensure_ascii=False, separators=(',', ':')),
                json.dumps(period, ensure_ascii=False, separators=(',', ':'))),)
        return WaveHourlySnapshot(resource, grid_code, analysis_date, hour, rows, SOURCE_URL,
                                  TYPES, datetime.now(timezone.utc))
