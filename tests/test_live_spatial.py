"""현재 공개 SDK 원문 ZIP을 GDAL로 전 행 파싱하는 opt-in live 테스트."""
import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest
pytestmark=[pytest.mark.live,pytest.mark.spatial]


async def test_live_downloaded_archives_gdal():
    from vadahub import VadaHubFileClient, DatasetLayer
    root=Path(os.environ['VADAHUB_LIVE_ARCHIVES'])
    report=json.loads((root/'t003-live.json').read_text(encoding='utf-8'))
    expected={'500048':34,'500059':424,'501297':38,'501298':142,'501304':109,'501991':110}
    results=[]
    async with VadaHubFileClient() as client:
        for receipt in report['downloads']:
            layer=DatasetLayer(**receipt['layer'])
            rows=await client.load_file(root/(layer.layer_id+'.zip'),layer=layer)
            assert len(rows)==expected[layer.layer_id]
            assert all(x.source_sha256 == receipt['sha256'] for x in rows)
            assert all(x.source_crs is None and x.wgs84_wkb is None for x in rows)
            if layer.layer_id=='500048':
                assert all(not x.attributes.get('oc_spce_obj_krnm') and not x.attributes.get('piltg_rute_dc') for x in rows)
            results.append({'layer_id':layer.layer_id,'count':len(rows),'source_sha256':rows[0].source_sha256,'crs':None})
    (root/'t004-gdal-live.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('실제 SDK ZIP→GDAL 전 행:',results)
