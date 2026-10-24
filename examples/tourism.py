"""공개 관광 ZIP 보관과 GDAL 검색. python examples/tourism.py --help 참조."""
import argparse
import asyncio
from pathlib import Path
from vadahub import VadaHubFileClient, LocalArchiveStore, tourism_from_feature, search_tourism, TOURISM_SOURCES


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('category', choices=[s.category for s in TOURISM_SOURCES])
    parser.add_argument('destination', type=Path, help='기존 파일이 아닌 신규 ZIP 경로')
    parser.add_argument('--store', type=Path, default=Path('vadahub-store'))
    parser.add_argument('--region')
    parser.add_argument('--chromium')
    parser.add_argument('--preserve-invalid', action='store_true', help='invalid 도형도 원 WKB/상태로 보존')
    args = parser.parse_args()
    async with VadaHubFileClient(timeout=120, executable_path=args.chromium) as client:
        selected = (await client.list_tourism_layers(args.category))[0]
        receipt = await client.download(selected.layer, args.destination)
        stored = await LocalArchiveStore(args.store).put(receipt)
        rows = await client.load_file(stored.receipt.local_path, layer=stored.receipt.layer,
            receipt=stored.receipt, invalid_geometry='preserve' if args.preserve_invalid else 'raise')
        places = (tourism_from_feature(row, category=args.category) for row in rows)
        for place in search_tourism(places, region_contains=args.region):
            print(place.name, place.address, place.survey_year, place.source_date, place.feature.geometry_valid)


if __name__ == '__main__':
    asyncio.run(main())
