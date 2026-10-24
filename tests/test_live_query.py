"""66개 안내의 공개 backing 자료 전수 질의와 작은 공간 ZIP live 검증."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import pytest
from vadahub import VadaHubFileClient, DownloadUnavailableError

pytestmark=pytest.mark.live


async def test_live_api_backing_resources_and_bounded_query(tmp_path):
    root=Path(os.environ.get('VADAHUB_QUERY_ARTIFACTS',str(tmp_path)));root.mkdir(parents=True,exist_ok=True)
    results=[]
    async with VadaHubFileClient(timeout=150,executable_path=os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')) as client:
        for kind in ('api_original','api_analysis','api_map'):
            services=await client.list_datasets(catalog=kind,page_size=100)
            for dataset in services:
                resources=await client.list_resources(dataset)
                result={'api_id':dataset.api_id,'catalog':kind,'catalog_meta':dataset.dataset_id,'title':dataset.title,'resources':[]}
                for resource in resources:
                    record={'resource_id':resource.resource_id,'backing_meta':resource.backing_dataset_id,'source_name':resource.source_name}
                    try:
                        page=await client.query_table(resource,page_size=1)
                        record.update(status='query_supported',total=page.total,rows=len(page.rows),columns=page.columns)
                    except DownloadUnavailableError as error:
                        record.update(status='source_grid_unavailable',reason=str(error))
                    result['resources'].append(record)
                if dataset.api_id=='147':
                    layers=await client.list_api_layers(dataset)
                    receipt=await client.download(layers[0],root/'api147.zip')
                    record=asdict(receipt);record['local_path']=receipt.local_path.name;record['collected_at']=receipt.collected_at.isoformat()
                    (root/'api147-receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                results.append(result)
                print(dataset.api_id,[r['status'] for r in result['resources']],flush=True)
                (root/'t007a2-live.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    assert len(results)==66
    assert any(r['status']=='query_supported' for result in results for r in result['resources'])
