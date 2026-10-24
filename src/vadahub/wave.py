"""인공지능 해양정보 공개 화면의 기간·격자 한정 파랑 통계."""
from __future__ import annotations

from datetime import date, datetime, timezone
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING

from ._browser import BASE_URL
from .exceptions import AccessDeniedError, SchemaError
from .models import WaveMeasure, WaveStatistic, WaveStatistics

if TYPE_CHECKING:
    from .client import VadaHubClient

SOURCE_URL = BASE_URL + '/analyze/marine/aipast/index.do'


async def get_wave3min_statistics(client: VadaHubClient, grid_code: str, *, start_date: date,
        end_date: date, measure: WaveMeasure) -> WaveStatistics:
    """원행 query_table과 독립된 공개 웹 통계. 실패 시 서로 fallback하지 않는다."""
    if (not isinstance(grid_code, str) or not re.fullmatch(r'GR3_[A-Z0-9_]{1,32}', grid_code)
            or type(start_date) is not date or type(end_date) is not date
            or not 0 <= (end_date - start_date).days <= 6 or measure not in ('height', 'period')):
        raise ValueError('GR3 격자1개, date 날짜 양끝 포함1~7일, height/period가 필요합니다')
    datasets = [d for d in await client.list_datasets(catalog='api_original') if d.api_id == '139']
    if len(datasets) != 1:
        raise SchemaError('API139 공개 안내가 없거나 중복입니다')
    resources = [r for r in await client.list_resources(datasets[0]) if r.resource_id == '520360']
    if len(resources) != 1:
        raise SchemaError('API139 파랑3분 연결자료 identity가 바뀌었습니다')
    async with client._browser.operation() as page:
        from .client import _open_page
        current = await client._current_resource(page, resources[0])
        if (current.source_name != 'opn_tb_grid_cont_wv_3min' or current.dataset.api_id != '139'
                or current.attribute_kind != 'SPATIAL' or not current.grid_available):
            raise SchemaError('공개 파랑3분 원천 계약이 바뀌었습니다')
        if current.service_auth != 'OPEN' or current.open_scope != 'ALL' or current.masked is not False:
            raise AccessDeniedError('파랑 통계의 공개/전체/비마스킹 상태가 필요합니다')
        await _open_page(page, SOURCE_URL, '.cont-wrapper')
        field = 'wvhgh' if measure == 'height' else 'pd'
        payload = await client._post(page, '/user/aiModel/selectGridStatsPastWv.do', {
            'gridNo': grid_code, 'ogType': 'grid_3_step_a', 'type': field,
            'startDate': start_date.isoformat().replace('-', ''),
            'endDate': end_date.isoformat().replace('-', ''), 'tableNm': 'WV_3MIN',
        })
        raw = payload.get('layerStatsWv')
        if not isinstance(raw, list) or len(raw) > (end_date - start_date).days + 1:
            raise SchemaError('파랑 웹 통계 목록/행수 계약 오류')
        result = []
        seen = set()
        for row in raw:
            if (not isinstance(row, dict) or not {'gridCd', 'analsYmd', field}.issubset(row)
                    or row['gridCd'] != grid_code or not isinstance(row['analsYmd'], str)
                    or not re.fullmatch(r'[0-9]{8}', row['analsYmd'])
                    or not all(isinstance(key, str) and (value is None or isinstance(value, (str, bool, int))
                        or isinstance(value, float) and math.isfinite(value)) for key, value in row.items())):
                raise SchemaError('파랑 웹 통계 행/격자/필드 계약 오류')
            raw_date = row['analsYmd']
            try:
                parsed = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
            except ValueError as exc:
                raise SchemaError('파랑 웹 통계 날짜 오류') from exc
            value = row[field]
            if (not start_date <= parsed <= end_date or parsed in seen
                    or value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)))):
                raise SchemaError('파랑 웹 통계 날짜범위/중복/측정값 오류')
            try:
                numeric = float(value) if value is not None else None
            except (OverflowError, ValueError) as exc:
                raise SchemaError('파랑 웹 통계 측정값 범위 오류') from exc
            if numeric is not None and not math.isfinite(numeric):
                raise SchemaError('파랑 웹 통계 측정값 범위 오류')
            seen.add(parsed)
            result.append(WaveStatistic(grid_code, parsed, numeric,
                MappingProxyType(dict(row))))
        return WaveStatistics(current, grid_code, start_date, end_date, measure, tuple(result),
            SOURCE_URL, datetime.now(timezone.utc))
