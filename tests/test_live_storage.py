"""공개 원문 보관·재실행·재로딩·manifest 실패 복구의 live gate."""
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import pytest
from vadahub import ArchiveReceipt, DatasetLayer, LocalArchiveStore, VadaHubFileClient

pytestmark=[pytest.mark.live,pytest.mark.spatial]


async def test_live_archive_versions_idempotency_and_recovery(tmp_path,monkeypatch):
    import vadahub.storage as module
    root=Path(os.environ['VADAHUB_LIVE_ARCHIVES'])
    source=json.loads((root/'t003-live.json').read_text(encoding='utf-8'))
    store=LocalArchiveStore(tmp_path/'store')
    count=0
    receipts=[]
    for item in source['downloads']:
        layer=DatasetLayer(**item['layer'])
        receipt=ArchiveReceipt(layer,item['source_url'],datetime.fromisoformat(item['collected_at']),
            item['sha256'],item['byte_size'],root/(layer.layer_id+'.zip'),tuple(tuple(x) for x in item['member_sha256']))
        stored=await store.put(receipt)
        assert await store.put(receipt)==stored
        assert await store.versions(layer)==(stored,)
        receipts.append(receipt)
        async with VadaHubFileClient() as client:
            rows=await client.load_file(stored.receipt.local_path,layer=layer,receipt=stored.receipt)
        count+=len(rows)
    assert count==857
    previous=(store.root/'manifest.json').read_bytes()
    # 별도 meta scope의 원문은 같은 payload라도 독립 버전으로 취급한다.
    scoped=replace(receipts[0],layer=replace(receipts[0].layer,dataset_id='999999'))
    original=module._atomic_json
    def fail(path,value):
        if path.name=='manifest.json': raise OSError('live simulated manifest failure')
        return original(path,value)
    monkeypatch.setattr(module,'_atomic_json',fail)
    with pytest.raises(OSError): await store.put(scoped)
    assert (store.root/'manifest.json').read_bytes()==previous
    monkeypatch.setattr(module,'_atomic_json',original)
    recovered=await store.recover()
    assert len(recovered)==1 and recovered[0].receipt.layer.dataset_id=='999999'
    report=dict(archive_count=6,parsed_rows=count,idempotent=True,orphan_recovered=True,
                hashes=[r.sha256 for r in receipts])
    (root/'t006-storage-live.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(report)
