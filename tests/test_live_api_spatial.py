"""공개 API 안내에서 받은 실제 SHP의 GDAL 파싱."""
from pathlib import Path
import os,json
import pytest
from vadahub import VadaHubFileClient, DatasetLayer
pytestmark=[pytest.mark.live,pytest.mark.spatial]


async def test_live_api144_downloaded_shapefile():
    root=Path(os.environ['VADAHUB_QUERY_ARTIFACTS'])
    receipt=json.loads((root/'api144-receipt.json').read_text(encoding='utf-8'))
    async with VadaHubFileClient() as client:
        rows=await client.load_file(root/'api144.zip',layer=DatasetLayer(**receipt['layer']))
    assert len(rows)==receipt['expected_rows'] and rows[0].source_sha256==receipt['sha256']
    print('API144 실제 SHP GDAL',len(rows),list(rows[0].attributes),rows[0].source_crs)
