"""실제 관광 ZIP 전 행을 GDAL로 읽고 요약·검색·원문 계보를 대조한다."""
from datetime import datetime
import json
import os
from pathlib import Path
import pytest
from vadahub import (VadaHubFileClient, DatasetLayer, ArchiveReceipt, SchemaError,
    tourism_from_feature, search_tourism)

pytestmark = [pytest.mark.live, pytest.mark.spatial]
EXPECTED = {'beach': 410, 'experience_village': 119, 'observatory': 112, 'freshwater_fishing': 554,
    'sea_fishing': 219, 'coastal_walk': 142, 'marina': 39, 'rock_fishing': 1076, 'experience_village_legacy': 226}


async def test_live_tourism_all_rows():
    root = Path(os.environ['VADAHUB_TOURISM_ARTIFACTS'])
    report = json.loads((root / 'tourism-receipts.json').read_text(encoding='utf-8'))
    assert {item['category'] for item in report} == set(EXPECTED)
    output = []
    async with VadaHubFileClient() as client:
        for record in report:
            category = record['category']
            layer = DatasetLayer(**record['layer'])
            path = root / record['local_path']
            receipt = ArchiveReceipt(layer, record['source_url'], datetime.fromisoformat(record['collected_at']),
                record['sha256'], record['byte_size'], path, tuple(tuple(pair) for pair in record['member_sha256']))
            if category == 'beach':
                with pytest.raises(SchemaError, match='geometry 유효성'):
                    await client.load_file(path, layer=layer, receipt=receipt)
            features = await client.load_file(path, layer=layer, receipt=receipt,
                invalid_geometry='preserve' if category == 'beach' else 'raise')
            places = [tourism_from_feature(row, category=category) for row in features]
            assert len(places) == EXPECTED[category]
            assert all(p.feature.source_sha256 == receipt.sha256 and p.feature.source_collected_at == receipt.collected_at for p in places)
            assert all(p.feature.source_crs is None and p.feature.wgs84_wkb is None for p in places)
            named = next(p for p in places if p.name)
            assert named in list(search_tourism(places, name_contains=named.name))
            invalid = sum(p.feature.geometry_valid is False for p in places)
            assert invalid == (2 if category == 'beach' else 0)
            if category == 'freshwater_fishing': assert any(p.name is None for p in places) and all(p.phone is None for p in places)
            if category == 'coastal_walk': assert all(p.feature.geometry_type == 'POINT' for p in places)
            output.append(dict(category=category, count=len(places), invalid=invalid,
                missing_names=sum(p.name is None for p in places), sha256=receipt.sha256,
                geometry_types=sorted({p.feature.geometry_type for p in places}),
                survey_years=sorted({p.survey_year for p in places if p.survey_year is not None}),
                source_dates=sorted({p.source_date.isoformat() for p in places if p.source_date is not None})))
            print(category, len(places), 'invalid', invalid, flush=True)
    assert sum(item['count'] for item in output) == 2897
    (root / 'tourism-gdal.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
