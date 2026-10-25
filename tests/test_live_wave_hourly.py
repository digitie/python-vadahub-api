"""실제 Chromium으로 복수 시각/격자의 파랑 투영 원값을 검증한다."""
from datetime import date
import json
import os
from pathlib import Path
import pytest
from vadahub import VadaHubClient

pytestmark = pytest.mark.live


async def test_live_hourly_values_and_empty(tmp_path):
    root = Path(os.environ.get('VADAHUB_HOURLY_ARTIFACTS', str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    report = []
    async with VadaHubClient(timeout=90, executable_path=os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')) as client:
        for grid, day, hour in [('GR3_F4J12_H', date(2018, 6, 10), 18),
            ('GR3_F4J12_H', date(2018, 6, 10), 21), ('GR3_F4J12_G', date(2018, 6, 10), 18),
            ('GR3_F4J12_H', date(1900, 1, 1), 18)]:
            result = await client.get_wave3min_hourly(grid, analysis_date=day, hour=hour)
            assert result.resource.dataset.api_id == '139' and result.resource.resource_id == '520360'
            if day.year == 1900:
                assert result.rows == ()
            else:
                assert len(result.rows) == 1
                row = result.rows[0]
                assert (row.grid_code, row.analysis_date, row.hour) == (grid, day, hour)
                assert row.wave_height is not None and row.mean_wave_period is not None
                if grid == 'GR3_F4J12_H' and hour == 18:
                    assert (row.wave_height, row.wave_direction, row.mean_wave_period) == (1.351, 132.001, 12.2)
            report.append({'grid_code': grid, 'analysis_date': day.isoformat(), 'hour': hour,
                'source_url': result.source_url, 'type_names': result.type_names,
                'collected_at': result.collected_at.isoformat(), 'rows': [
                    {'height': dict(r.height_attributes), 'period': dict(r.period_attributes),
                     'height_fid': r.height_fid, 'period_fid': r.period_fid,
                     'height_feature_json': r.height_feature_json, 'period_feature_json': r.period_feature_json}
                    for r in result.rows]})
    (root / 'hourly-live.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
