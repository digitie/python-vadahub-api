"""공개 SDK의 카탈로그→전체 layer→6 ZIP 및 미제공 상태 live E2E."""
import json
import os
from pathlib import Path
from dataclasses import asdict

import pytest
from vadahub import VadaHubFileClient, DownloadUnavailableError

pytestmark=pytest.mark.live


async def test_live_catalog_and_public_downloads(tmp_path):
    output=Path(os.environ.get('VADAHUB_LIVE_ARTIFACTS',str(tmp_path)))
    output.mkdir(parents=True,exist_ok=True)
    targets={'관광지정보','여객터미널','도선항로','여객항로'}
    receipts=[]; unavailable=[]
    async with VadaHubFileClient(executable_path=os.getenv('VADAHUB_CHROMIUM_EXECUTABLE'),timeout=120) as client:
        catalog=await client.list_datasets()
        selected=[x for x in catalog if x.title in targets]
        assert len(selected)==4
        layers=[]
        for dataset in selected: layers.extend(await client.list_layers(dataset))
        assert len(layers)==7
        for layer in layers:
            destination=output/f'{layer.layer_id}.zip'
            if not layer.download_available:
                with pytest.raises(DownloadUnavailableError): await client.download(layer,destination)
                unavailable.append(layer.layer_id)
            else:
                receipt=await client.download(layer,destination)
                receipts.append(asdict(receipt))
                assert receipt.byte_size>0 and len(receipt.member_sha256)>=4
    assert len(receipts)==6 and unavailable==['501880']
    report={'catalog_total':len(catalog),'downloads':receipts,'unavailable':unavailable}
    (output/'t003-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(f'공간 카탈로그 {len(catalog)}, 7 layer, 6 ZIP, terminal 미제공 확인')
