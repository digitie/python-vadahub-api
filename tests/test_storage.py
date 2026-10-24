"""immutable 원문·원자 manifest·중복과 실패 복구를 검증한다."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import zipfile
import pytest
from vadahub import ArchiveLimits, ArchiveReceipt, DatasetLayer, LocalArchiveStore, ArchiveError
from vadahub._archive import inspect_archive

LAYER=DatasetLayer('52','2019-12-10','500048','piltg_rute_l','도선항로','OPEN','ALL',True,True)


def receipt(tmp_path, *, payload=b'original',year=2020):
    path=tmp_path/('source-'+str(year)+'.zip')
    with zipfile.ZipFile(path,'w') as z:
        for ext in ('shp','shx','dbf','txt'):
            info=zipfile.ZipInfo('piltg_rute_l.'+ext,date_time=(year,1,1,0,0,0))
            z.writestr(info,payload)
    checksum,members=inspect_archive(path,ArchiveLimits(),LAYER.table_name)
    return ArchiveReceipt(LAYER,LAYER.source_url,datetime.now(timezone.utc),checksum,path.stat().st_size,path,members)


async def test_roundtrip_idempotency_payload_fingerprint(tmp_path):
    store=LocalArchiveStore(tmp_path/'store')
    first=receipt(tmp_path)
    stored=await store.put(first)
    assert stored.receipt.local_path.read_bytes()==first.local_path.read_bytes()
    assert stored.object_key.endswith(first.sha256)
    assert await store.put(replace(first,collected_at=datetime.now(timezone.utc)))==stored
    repacked=await store.put(receipt(tmp_path,year=2021))
    assert repacked.receipt.sha256!=stored.receipt.sha256 and repacked.content_fingerprint==stored.content_fingerprint
    changed=await store.put(receipt(tmp_path,year=2022,payload=b'changed'))
    assert changed.content_fingerprint!=stored.content_fingerprint
    assert await store.versions(LAYER)==(stored,repacked,changed)
    assert await store.recover()==()


async def test_manifest_failure_keeps_previous_then_recovers(tmp_path,monkeypatch):
    import vadahub.storage as module
    store=LocalArchiveStore(tmp_path/'store')
    first=await store.put(receipt(tmp_path))
    previous=(store.root/'manifest.json').read_bytes()
    second=receipt(tmp_path,year=2021,payload=b'changed')
    original=module._atomic_json
    def failed_manifest(path,value):
        if path.name=='manifest.json': raise OSError('simulated disk failure')
        original(path,value)
    monkeypatch.setattr(module,'_atomic_json',failed_manifest)
    with pytest.raises(OSError): await store.put(second)
    assert (store.root/'manifest.json').read_bytes()==previous
    assert await store.versions(LAYER)==(first,)
    monkeypatch.setattr(module,'_atomic_json',original)
    recovered=await store.recover()
    assert len(recovered)==1 and recovered[0].receipt.sha256==second.sha256
    assert len(await store.versions(LAYER))==2


async def test_corruption_never_silently_replaced(tmp_path):
    store=LocalArchiveStore(tmp_path/'store')
    source=receipt(tmp_path)
    stored=await store.put(source)
    stored.receipt.local_path.write_bytes(b'corrupt')
    with pytest.raises(ArchiveError): await store.put(source)
    with pytest.raises(ArchiveError): await store.versions(LAYER)
    with pytest.raises(ArchiveError): await store.recover()
    assert stored.receipt.local_path.read_bytes()==b'corrupt'


@pytest.mark.parametrize('names',[('archive.zip',),('receipt.json',),('archive.zip','receipt.json')])
async def test_recover_reports_missing_manifest_objects(tmp_path,names):
    store=LocalArchiveStore(tmp_path/'store')
    stored=await store.put(receipt(tmp_path))
    manifest=(store.root/'manifest.json').read_bytes()
    for name in names: (stored.receipt.local_path.parent/name).unlink()
    with pytest.raises(ArchiveError): await store.recover()
    with pytest.raises(ArchiveError): await store.versions(LAYER)
    assert (store.root/'manifest.json').read_bytes()==manifest


async def test_wrong_receipt_and_manifest_schema(tmp_path):
    source=receipt(tmp_path)
    store=LocalArchiveStore(tmp_path/'store')
    for item in (replace(source,sha256='a'*64),replace(source,byte_size=1),replace(source,member_sha256=()),
                 replace(source,collected_at=datetime.now()),replace(source,sha256='bad')):
        with pytest.raises(ArchiveError): await store.put(item)
    assert not (store.root/'manifest.json').exists()
    assert list((store.root/'.staging').iterdir())==[]
    store.root.joinpath('manifest.json').write_text('{invalid')
    with pytest.raises(ArchiveError): await store.versions(LAYER)
    store.root.joinpath('manifest.json').write_text(json.dumps({'schema_version':'2','entries':{}}))
    with pytest.raises(ArchiveError): await store.recover()


async def test_cancel_stage_does_not_publish(tmp_path,monkeypatch):
    store=LocalArchiveStore(tmp_path/'store')
    source=receipt(tmp_path)
    entered,release=threading.Event(),threading.Event()
    original=store._prepare
    def slow(*args):
        entered.set(); release.wait(); original(*args)
    monkeypatch.setattr(store,'_prepare',slow)
    task=asyncio.create_task(store.put(source))
    await asyncio.to_thread(entered.wait)
    task.cancel(); await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError): await task
    assert not (store.root/'manifest.json').exists()
    assert list((store.root/'.staging').iterdir())==[]


async def test_concurrent_writers_same_root_preserve_both(tmp_path):
    root=tmp_path/'store'
    first,second=receipt(tmp_path),receipt(tmp_path,year=2021,payload=b'changed')
    await asyncio.gather(LocalArchiveStore(root).put(first),LocalArchiveStore(root).put(second))
    assert {v.receipt.sha256 for v in await LocalArchiveStore(root).versions(LAYER)}=={first.sha256,second.sha256}


@pytest.mark.parametrize('timeout',[0,-1,float('inf'),True])
def test_bad_lock_timeout(tmp_path,timeout):
    with pytest.raises(ValueError): LocalArchiveStore(tmp_path,lock_timeout=timeout)


@pytest.mark.parametrize('value',[None,{}, {'schema_version':'1'},
    {'schema_version':'1','layer':{}}, {'schema_version':'1','layer':dict()},
])
def test_bad_receipt_schema(tmp_path,value):
    with pytest.raises(ArchiveError): LocalArchiveStore(tmp_path)._decode(value)
