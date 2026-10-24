"""실제 공개 날짜·격자 파랑 통계. 일반 DataTables 원행 성공으로 집계하지 않는다."""
from datetime import date
import json
import os
from pathlib import Path
import pytest
from vadahub import VadaHubClient

pytestmark = pytest.mark.live


async def test_live_wave3min_statistics(tmp_path):
    root = Path(os.environ.get('VADAHUB_WAVE_ARTIFACTS', str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    report = []
    async with VadaHubClient(timeout=60, executable_path=os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')) as client:
        for measure in ('height', 'period'):
            result = await client.get_wave3min_statistics('GR3_F4J12_H', start_date=date(2018, 6, 10),
                end_date=date(2018, 6, 11), measure=measure)
            assert result.resource.dataset.api_id == '139' and result.measure == measure and len(result.rows) == 2
            assert all(row.grid_code == result.grid_code and row.value is not None for row in result.rows)
            report.append({'measure': measure, 'source_url': result.source_url,
                'api_id': result.resource.dataset.api_id, 'resource_id': result.resource.resource_id,
                'collected_at': result.collected_at.isoformat(),
                'rows': [dict(row.raw_attributes) for row in result.rows]})
    (root / 'wave-live.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
