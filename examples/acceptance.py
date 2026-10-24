"""설치본의 실제 catalog→ZIP→GDAL→매핑→보관 재로딩 수용 검증. 신규 --output 경로를 지정한다."""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import vadahub
from vadahub import (ArchiveReceipt, VadaHubFileClient, LocalArchiveStore, DownloadUnavailableError,
    ports_from_features, map_route, search_tourism)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='기존에 없는 디렉터리')
    parser.add_argument('--chromium', help='기본 Playwright Chromium 대신 사용할 실행 파일')
    args = parser.parse_args()
    root = args.output.absolute()
    root.mkdir(parents=True, exist_ok=False)
    store = LocalArchiveStore(root / 'store')
    report = {'version': version('python-vadahub-api'), 'collected_at': datetime.now(timezone.utc).isoformat(),
        'module': str(Path(vadahub.__file__).resolve()), 'downloads': []}
    loaded = {}
    async with VadaHubFileClient(timeout=120, executable_path=args.chromium) as client:
        catalog = await client.list_datasets()
        selected = [d for d in catalog if d.dataset_id in ('52', '63', '3076', '5055')]
        assert len(selected) == 4, '지정 meta 원천 변경'
        layers = [layer for dataset in selected for layer in await client.list_layers(dataset)]
        assert len(layers) == 7, '지정 layer 원천 변경'
        unavailable = []
        for layer in layers:
            path = root / (layer.layer_id + '.zip')
            if layer.layer_id == '501880':
                try:
                    await client.download(layer, path)
                except DownloadUnavailableError:
                    unavailable.append(layer.layer_id)
                    continue
                raise AssertionError('터미널 다운로드 원천이 바뀌었습니다. 사양을 재검토하세요')
            receipt = await client.download(layer, path)
            stored = await store.put(receipt)
            assert stored == await store.put(receipt), '동일 원문 보관 멱등성 실패'
            assert await store.versions(layer) == (stored,)
            assert isinstance(stored.receipt, ArchiveReceipt)
            rows = await client.load_file(stored.receipt.local_path, layer=layer, receipt=stored.receipt)
            assert all(row.source_sha256 == receipt.sha256 and row.source_collected_at == receipt.collected_at for row in rows)
            assert all(row.source_crs is None and row.wgs84_wkb is None for row in rows), '원천 CRS가 바뀌었습니다'
            loaded[layer.layer_id] = rows
            record = asdict(receipt)
            record.update(local_path=path.name, collected_at=receipt.collected_at.isoformat(), rows=len(rows))
            report['downloads'].append(record)
            print(layer.table_name, len(rows), receipt.sha256, flush=True)
        assert len(report['downloads']) == 6 and unavailable == ['501880']
        assert sum(len(rows) for rows in loaded.values()) == 857, '기준 snapshot 수량 변경'
        piers = ports_from_features(loaded['501304'])
        assert len(piers) == 109 and all(p.kind == 'facility' for p in piers)
        ferry = [map_route(row, ports=piers, endpoint_kind='pier') for row in loaded['500048']]
        assert len(ferry) == 34 and all(r.departure.status == r.arrival.status == 'missing_endpoints' for r in ferry)
        passenger = [map_route(row, ports=piers, endpoint_kind='pier') for row in loaded['500059']]
        assert len(passenger) == 424 and all(r.endpoints.scope == 'whole_route' for r in passenger)
        # 실제 도선 실매핑·터미널 SHP 확보가 아닌 명시적 결측/역할 계약을 확인한다.
        report['mapping'] = {'do_seon_rows': 34, 'missing_endpoints': 34, 'passenger_rows': 424,
            'facility_candidates': 109, 'actual_do_seon_mapping_verified': False}
        report['terminal_download'] = 'source_unavailable'
        villages = await client.load_tourism('experience_village')
        beaches = await client.load_tourism('beach', invalid_geometry='preserve')
        assert len(villages) == 119 and len(beaches) == 410
        assert list(search_tourism(villages, region_contains='삼척'))
        assert sum(p.feature.geometry_valid is False for p in beaches) == 2
        report['tourism'] = {'experience_village': len(villages), 'beach': len(beaches), 'invalid_beach': 2,
            'hashes': [villages[0].feature.source_sha256, beaches[0].feature.source_sha256]}
        apis = await client.list_datasets(catalog='api_original')
        api = next(d for d in apis if d.api_id == '124')
        resource = (await client.list_resources(api))[0]
        page = await client.query_table(resource, page_size=1)
        assert page.rows
        gid = page.rows[0]['gid']
        filtered = await client.query_table(resource, page_size=1, filters={'gid': str(gid)})
        assert filtered.rows and filtered.rows[0]['gid'] == gid and 0 < filtered.filtered_total < page.total
        report['web_query'] = {'api_id': api.api_id, 'resource_id': resource.resource_id,
            'total_raw': page.total, 'filtered_total_raw': filtered.filtered_total, 'filter_verified': True}
    assert await store.recover() == ()
    report['archive_rows'] = 857
    report['store_idempotent'] = True
    report['constraints'] = ['T005E: 도선 출도착지/여객터미널 SHP 미확보', 'T007A2E: API139 조회 미확인']
    (root / 'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('설치본 실제 수용 검증 통과: ZIP6/857행 + 관광529행 + API124 필터; 외부제약은 미해결', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
