"""실제 다운로드 원문과 명시적인 transport 계약 fixture를 연결한다."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import pytest
from vadahub import VadaHubFileClient, DatasetLayer, ports_from_features, map_route, port_from_transport

pytestmark=[pytest.mark.live,pytest.mark.spatial]


async def test_live_raw_routes_and_pier_mapping_contract():
    root=Path(os.environ['VADAHUB_LIVE_ARCHIVES'])
    report=json.loads((root/'t003-live.json').read_text(encoding='utf-8'))
    layers={r['layer']['layer_id']:DatasetLayer(**r['layer']) for r in report['downloads']}
    async with VadaHubFileClient() as client:
        ferry=await client.load_file(root/'500048.zip',layer=layers['500048'])
        passenger=await client.load_file(root/'500059.zip',layer=layers['500059'])
        piers=ports_from_features(await client.load_file(root/'501304.zip',layer=layers['501304']))
    assert len(ferry)==34 and len(passenger)==424 and len(piers)==109
    for row in ferry:
        result=map_route(row,ports=piers,endpoint_kind='pier')
        assert result.departure.status==result.arrival.status=='missing_endpoints'
    assert all(p.latitude is None and p.feature is not None for p in piers)
    sample=next(row for row in passenger if row.record_id=='42')
    # 가공한 계약 fixture이며 실제 TAGO 항구 코드를 검증했다는 주장이 아니다.
    reference=port_from_transport(dict(natural_key='contract_fixture:fixture_hari',source='contract_fixture',
        port_id='fixture_hari',name='하리',latitude=None,longitude=None,location_source=None,
        admin={'legal_dong_code':'2811000000'}),collected_at=datetime.now(timezone.utc),source_url='https://example.org/contract-fixture')
    result=map_route(sample,ports=[reference],departure_region='2811000000')
    assert result.departure.status=='matched' and result.arrival.status=='unmatched'
    assert result.endpoints.arrival=='서검' and result.endpoints.segment_name=='하리-미법'
    receipt=dict(ferry_count=len(ferry),missing_ferry_endpoints=34,passenger_count=len(passenger),pier_count=len(piers),
        source_hashes={row.layer.layer_id:row.source_sha256 for row in (ferry[0],passenger[0],piers[0].feature)},
        mapping_reference='contract_fixture; not an actual transport export',sample_departure_status=result.departure.status)
    (root/'t005-mapping-live.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(receipt)
