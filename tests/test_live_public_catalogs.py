"""공개 5종 안내/자료실·PDF URL·통계 snapshot·ZIP 보관 live 검증."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import pytest
from vadahub import VadaHubFileClient, LocalArchiveStore, AccessDeniedError

pytestmark=pytest.mark.live


async def test_live_public_catalogs_preview_and_library_archive(tmp_path):
    root=Path(os.environ.get('VADAHUB_PUBLIC_ARTIFACTS',str(tmp_path)))
    root.mkdir(parents=True,exist_ok=True)
    report={'counts':{},'api_services':[]}
    async with VadaHubFileClient(timeout=150,executable_path=os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')) as client:
        for kind,expected in [('api_original',40),('api_analysis',25),('api_map',1),('documents',451),('statistics',73)]:
            rows=await client.list_datasets(catalog=kind,page_size=100)
            assert len(rows)==expected and all(row.catalog==kind for row in rows)
            report['counts'][kind]=len(rows)
            if kind.startswith('api_'):
                report['api_services'].extend(asdict(row) for row in rows)
            if kind=='documents':
                pdf_dataset=next(row for row in rows if row.dataset_id=='1297')
                resource=(await client.list_resources(pdf_dataset))[0]
                preview=await client.get_document_preview(resource)
                assert preview.preview_url.startswith('https://vadahub.go.kr/resource/publish/pdf/')
                assert not resource.download_available
                report['pdf_preview']={'resource_id':resource.resource_id,'url':preview.preview_url,'download_available':False}
                survey=next(row for row in rows if row.dataset_id=='700101')
                resources=await client.list_resources(survey)
                public=next(item for item in resources if item.resource_id=='720006')
                receipt=await client.download_library(public,root/'coastal-basic-survey.zip')
                stored=await LocalArchiveStore(root/'store').put(receipt)
                assert await LocalArchiveStore(root/'store').put(receipt)==stored
                report['library_archive']=asdict(receipt)
                report['library_archive']['local_path']=receipt.local_path.name
                report['library_archive']['collected_at']=receipt.collected_at.isoformat()
                report['stored_object']=stored.object_key
                private=next(item for item in resources if item.service_auth=='PRIVATE')
                with pytest.raises(AccessDeniedError):await client.download_library(private,root/'private.zip')
                assert not (root/'private.zip').exists()
            if kind=='statistics':
                dataset=next(row for row in rows if row.dataset_id=='20027')
                resource=(await client.list_resources(dataset))[0]
                snapshot=await client.get_table_preview(resource)
                assert snapshot.partial and snapshot.rows and snapshot.columns
                report['table_preview']={'resource_id':resource.resource_id,'rows':len(snapshot.rows),'columns':snapshot.columns,'partial':True}
    (root/'t007a-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(report['counts'],report['table_preview'],report['stored_object'])
