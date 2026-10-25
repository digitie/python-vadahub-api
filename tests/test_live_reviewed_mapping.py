"""새 공식 CSV와 같은 실행의 SHP를 GDAL로 읽어 실제 검토 매핑·보관을 검증한다."""
from dataclasses import asdict
from datetime import date, datetime
import json
import os
from pathlib import Path
import pytest
from vadahub import (OfficialPierClient, PierFileReceipt, VadaHubFileClient, DatasetLayer,
    ArchiveReceipt, LocalArchiveStore, pier_to_port, reviewed_route_crosswalks, map_route)

pytestmark = [pytest.mark.live, pytest.mark.spatial]


async def test_live_reviewed_route_and_pier_store():
    root = Path(os.environ['VADAHUB_PIER_ARTIFACTS'])
    raw = json.loads((root/'pier-live.json').read_text(encoding='utf-8')); raw.pop('rows')
    raw.update(local_path=root/'piers.csv', content_date=date.fromisoformat(raw['content_date']),
               collected_at=datetime.fromisoformat(raw['collected_at']))
    receipt = PierFileReceipt(**raw)
    store = LocalArchiveStore(root/'store')
    stored = await store.put(receipt)
    assert isinstance(stored.receipt, PierFileReceipt)
    assert await store.put(receipt) == stored
    (store.root/'manifest.json').unlink()
    assert len(await store.recover()) == 1 and await store.versions(receipt) == (stored,)
    async with OfficialPierClient() as client:
        piers = await client.load_file(stored.receipt.local_path, receipt=stored.receipt)
    archive_root = Path(os.environ['VADAHUB_LIVE_ARCHIVES'])
    spatial = json.loads((archive_root/'t003-live.json').read_text(encoding='utf-8'))
    item = next(r for r in spatial['downloads'] if r['layer']['layer_id'] == '500048')
    layer = DatasetLayer(**item.pop('layer'))
    item.update(local_path=archive_root/'500048.zip', collected_at=datetime.fromisoformat(item['collected_at']),
                member_sha256=tuple(tuple(pair) for pair in item['member_sha256']))
    archive = ArchiveReceipt(layer=layer, **item)
    async with VadaHubFileClient() as files:
        features = await files.load_file(archive.local_path, layer=layer, receipt=archive)
    results = []
    ports = [pier_to_port(p) for p in piers if p.name]
    for feature in features:
        crosswalk = reviewed_route_crosswalks(feature, receipt=archive, piers=piers)
        result = map_route(feature, ports=ports, crosswalk=crosswalk, endpoint_kind='pier')
        if feature.record_id == '2':
            assert result.departure.port and result.departure.port.name == '국동'
            assert result.arrival.port and result.arrival.port.name == '외동'
            assert result.endpoints.departure is None and result.endpoints.arrival is None
            assert result.departure.port.latitude is result.arrival.port.latitude is None
            results.append({'record_id': feature.record_id, 'departure': asdict(result.departure.port),
                'arrival': asdict(result.arrival.port), 'crosswalk': [asdict(c) for c in crosswalk],
                'source_crs': feature.source_crs, 'original_endpoints': asdict(result.endpoints)})
        else:
            assert not crosswalk and result.departure.status == result.arrival.status == 'missing_endpoints'
    assert len(features) == 34 and len(results) == 1 and len(piers) == 340
    report = {'pier_csv_sha256': receipt.sha256, 'archive_sha256': archive.sha256,
        'mapped': 1, 'unresolved': 33, 'pier_rows': 340, 'results': results}
    (root/'reviewed-mapping-live.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print('공식 선착장340행→GDAL도선34행→국동/외동1건 연결·33미확정·원자 보관/멱등/고아복구 통과')
