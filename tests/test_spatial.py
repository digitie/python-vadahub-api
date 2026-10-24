"""실제 GDAL fixture로 필드 매핑·좌표·worker·실패 경계를 검증한다."""
import asyncio
from contextlib import aclosing
from datetime import date, datetime, timezone
from dataclasses import replace
from pathlib import Path
import threading
from unittest.mock import AsyncMock
import zipfile

import pytest
pytest.importorskip('osgeo', reason='GDAL 검증은 필수 spatial CI/로컬 WSL에서 실행')
pytestmark=pytest.mark.spatial
from osgeo import gdal, ogr, osr
from vadahub import (VadaHubFileClient, ArchiveLimits, ArchiveReceipt, DatasetLayer,
                     SchemaError, UnknownCrsError)
from vadahub._archive import inspect_archive
from vadahub.parse import _field_mapping, _value

LAYER=DatasetLayer('52','2019-12-10','500048','piltg_rute_l','도선항로','OPEN','ALL',True,True)


def archive(tmp_path, *, srid=None, count=3, duplicate=False, bad_date=False, null=False):
    directory=tmp_path/'source'; directory.mkdir(exist_ok=True)
    path=directory/(LAYER.table_name+'.shp')
    ref=None
    if srid:
        with osr.ExceptionMgr():
            ref=osr.SpatialReference(); ref.ImportFromEPSG(srid)
    with gdal.ExceptionMgr(), ogr.ExceptionMgr():
        ds=ogr.GetDriverByName('ESRI Shapefile').CreateDataSource(str(path))
        layer=ds.CreateLayer(LAYER.table_name,srs=ref,geom_type=ogr.wkbPoint,options=['ENCODING=CP949'])
        for name,kind in [('c1',ogr.OFTInteger),('c3',ogr.OFTString),('c4',ogr.OFTString),('c5',ogr.OFTString)]:
            layer.CreateField(ogr.FieldDefn(name,kind))
        for i in range(count):
            feature=ogr.Feature(layer.GetLayerDefn())
            for name,value in [('c1',1 if duplicate else i+1),('c3','001'),('c4','선착장'),('c5','20261301' if bad_date else '20261024')]:
                feature.SetField(name,value)
            if not null: feature.SetGeometry(ogr.CreateGeometryFromWkt('POINT (126 37)'))
            layer.CreateFeature(feature)
            feature=None
        layer=None; ds=None
    mapping='\n'.join('{inFieldName='+k+', columnName='+v+', columnDescription=필드}' for k,v in
                       [('c1','gid'),('c3','code'),('c4','name'),('c5','mfgg_ymd')])
    (directory/(LAYER.table_name+'.txt')).write_bytes(mapping.encode('cp949'))
    output=tmp_path/'sample.zip'
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for member in directory.iterdir(): z.write(member,member.name)
    return output


async def test_real_gdal_raw_unknown_crs_and_dates(tmp_path):
    path=archive(tmp_path)
    async with VadaHubFileClient() as client:
        rows=await client.load_file(path,layer=LAYER)
    assert len(rows)==3 and rows[0].attributes['code']=='001'
    assert rows[0].attributes['name']=='선착장' and rows[0].attributes['mfgg_ymd']==date(2026,10,24)
    assert rows[0].raw_attributes['c5']=='20261024' and rows[0].record_id=='1'
    assert rows[0].geometry_type=='POINT' and rows[0].source_crs is None and rows[0].wgs84_wkb is None
    with pytest.raises(TypeError): rows[0].attributes['name']='mutate'


async def test_prj_axis_order_and_conflict(tmp_path):
    path=archive(tmp_path,srid=4326)
    async with VadaHubFileClient() as c:
        rows=await c.load_file(path,layer=LAYER)
        assert rows[0].crs_evidence=='archive_prj'
        point=ogr.CreateGeometryFromWkb(rows[0].wgs84_wkb)
        assert point.GetX()==126 and point.GetY()==37
        with pytest.raises(UnknownCrsError): await c.load_file(path,layer=LAYER,source_crs='EPSG:5179')
        with pytest.raises(UnknownCrsError): await c.load_file(path,layer=LAYER,source_crs='not a crs')


async def test_explicit_crs_receipt_and_remote_load(tmp_path,monkeypatch):
    path=archive(tmp_path,null=True)
    checksum,members=inspect_archive(path,ArchiveLimits(),LAYER.table_name)
    receipt=ArchiveReceipt(LAYER,LAYER.source_url,datetime.now(timezone.utc),checksum,path.stat().st_size,path,members)
    async with VadaHubFileClient() as c:
        rows=await c.load_file(path,layer=LAYER,source_crs='EPSG:4326',receipt=receipt)
        assert rows[0].geometry_wkb is None and rows[0].source_collected_at==receipt.collected_at
        assert rows[0].crs_evidence=='caller:EPSG:4326'
        with pytest.raises(SchemaError): await c.load_file(path,layer=LAYER,receipt=replace(receipt,sha256='bad'))
        monkeypatch.setattr(c,'download',AsyncMock(return_value=receipt))
        assert len(await c.load(LAYER))==3


@pytest.mark.parametrize('kwargs',[{'duplicate':True},{'bad_date':True}])
async def test_bad_records_never_silently_drop(tmp_path,kwargs):
    path=archive(tmp_path,**kwargs)
    async with VadaHubFileClient() as c:
        with pytest.raises(SchemaError): await c.load_file(path,layer=LAYER)


async def test_feature_cap_early_close_and_native_same_thread(tmp_path,monkeypatch):
    import vadahub.parse as module
    path=archive(tmp_path,count=40)
    thread_ids=[]; original=module._iter_sync
    def monitored(*args):
        for item in original(*args): thread_ids.append(threading.get_ident()); yield item
    monkeypatch.setattr(module,'_iter_sync',monitored)
    async with VadaHubFileClient() as c:
        with pytest.raises(SchemaError): await c.load_file(path,layer=LAYER,max_features=1)
        async with aclosing(c.iter_file(path,layer=LAYER,batch_size=1)) as stream:
            await anext(stream)
    assert len(set(thread_ids))==1
    assert thread_ids[0]!=threading.get_ident()


async def test_cancel_waits_until_worker_releases_dataset(tmp_path,monkeypatch):
    import vadahub.parse as module
    path=archive(tmp_path)
    started,release,finished=threading.Event(),threading.Event(),threading.Event()
    original=module._iter_sync
    def stalled(*args):
        started.set(); release.wait()
        try: yield from original(*args)
        finally: finished.set()
    monkeypatch.setattr(module,'_iter_sync',stalled)
    async with VadaHubFileClient() as c:
        stream=c.iter_file(path,layer=LAYER)
        task=asyncio.create_task(anext(stream))
        await asyncio.to_thread(started.wait)
        task.cancel(); await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError): await task
        assert finished.is_set()


@pytest.mark.parametrize('kwargs',[{'batch_size':0},{'batch_size':True},{'max_features':0}])
async def test_iterator_invalid_limits(tmp_path,kwargs):
    async with VadaHubFileClient() as c:
        with pytest.raises(ValueError):
            await anext(c.iter_file(tmp_path/'absent.zip',layer=LAYER,**kwargs))


@pytest.mark.parametrize('text,fields',[
    ('',{'c1'}),('{inFieldName=c1, columnName=gid}{inFieldName=c1, columnName=x}',{'c1'}),
    ('{inFieldName=c1, columnName=gid}{inFieldName=c2, columnName=gid}',{'c1','c2'}),
    ('{inFieldName=c1, columnName= }',{'c1'}),
])
def test_txt_mapping_errors(text,fields):
    with pytest.raises(SchemaError): _field_mapping(text,fields)


@pytest.mark.parametrize('value',['20260230','123',123])
def test_date_errors(value):
    with pytest.raises(SchemaError): _value('mfgg_ymd',value)
