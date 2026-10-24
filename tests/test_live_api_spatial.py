"""공개 API 안내에서 받은 실제 SHP의 GDAL 파싱."""
from pathlib import Path
import os,json
import pytest
from vadahub import VadaHubFileClient, DatasetLayer, SchemaError
pytestmark=[pytest.mark.live,pytest.mark.spatial]


async def test_live_api144_downloaded_shapefile():
    root=Path(os.environ['VADAHUB_QUERY_ARTIFACTS'])
    receipt=json.loads((root/'api144-receipt.json').read_text(encoding='utf-8'))
    async with VadaHubFileClient() as client:
        with pytest.raises(SchemaError,match='geometry 유효성'):
            await client.load_file(root/'api144.zip',layer=DatasetLayer(**receipt['layer']))
        rows=await client.load_file(root/'api144.zip',layer=DatasetLayer(**receipt['layer']),invalid_geometry='preserve')
    assert len(rows)==receipt['expected_rows'] and rows[0].source_sha256==receipt['sha256']
    invalid=sum(row.geometry_valid is False for row in rows)
    assert invalid>0 and all(row.wgs84_wkb is None for row in rows if row.geometry_valid is False)
    (root/'api144-gdal.json').write_text(json.dumps({'count':len(rows),'invalid_geometry':invalid,'sha256':rows[0].source_sha256}),encoding='utf-8')
    print('API144 실제 SHP GDAL',len(rows),'invalid',invalid,rows[0].source_crs)
