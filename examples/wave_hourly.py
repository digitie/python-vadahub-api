"""설치된 wheel의 공개 시각별 파랑 원값 소비 예제."""
import asyncio
from datetime import date
import json
import os
from vadahub import VadaHubClient


async def main() -> None:
    async with VadaHubClient(timeout=90, executable_path=os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')) as client:
        result = await client.get_wave3min_hourly('GR3_F4J12_H', analysis_date=date(2018, 6, 10), hour=18)
        row, = result.rows
        assert (row.wave_height, row.wave_direction, row.mean_wave_period) == (1.351, 132.001, 12.2)
        print(json.dumps({'api': result.resource.dataset.api_id, 'grid': row.grid_code,
            'date': row.analysis_date.isoformat(), 'hour': row.hour, 'height': row.wave_height,
            'direction': row.wave_direction, 'period': row.mean_wave_period,
            'source_url': result.source_url, 'collected_at': result.collected_at.isoformat()}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
