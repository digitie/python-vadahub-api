"""공개 날짜·격자 파랑 통계. 시간별 원행과 구분해서 출력한다."""
import argparse
import asyncio
from datetime import date
from vadahub import VadaHubClient


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('grid_code')
    parser.add_argument('start_date', type=date.fromisoformat)
    parser.add_argument('end_date', type=date.fromisoformat)
    parser.add_argument('--measure', choices=('height', 'period'), default='height')
    parser.add_argument('--chromium')
    args = parser.parse_args()
    async with VadaHubClient(timeout=60, executable_path=args.chromium) as client:
        result = await client.get_wave3min_statistics(args.grid_code, start_date=args.start_date,
            end_date=args.end_date, measure=args.measure)
        for row in result.rows:
            print(row.grid_code, row.analysis_date, row.value)
        print(result.source_url, result.collected_at)


if __name__ == '__main__':
    asyncio.run(main())
