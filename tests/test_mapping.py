"""transport 참조 계약과 오매핑 방지 경계를 검증한다."""
from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType
import pytest
from vadahub import (SpatialFeature, DatasetLayer, PortReference, EndpointCrosswalk,
                     SchemaError, route_endpoints, ports_from_features, port_from_transport, map_route)


def feature(table='psnr_rute_l', **attrs):
    layer=DatasetLayer('63','2019-12-10','500059',table,'여객항로','OPEN','ALL',True,True)
    return SpatialFeature(layer,'42','gid',MappingProxyType({}),MappingProxyType(attrs),
                          b'raw','LINESTRING',None,None,None,'a'*64)


def crosswalk(row, **kwargs):
    values=dict(dataset_id=row.layer.dataset_id,history_date=row.layer.history_date,layer_id=row.layer.layer_id,
                record_id=row.record_id,source_sha256=row.source_sha256,role='departure',endpoint_name='하리',
                target_source='tago',target_port_id='SEA001',evidence_url='https://example.org/evidence',
                evidence_record='survey-42',revision='review1')
    return EndpointCrosswalk(**(values|kwargs))


def test_whole_route_and_segment_are_separate():
    row=feature(strpnt_nm='하리',dstntn_nm='서검',prtcl_nm='미법',psnr_rute_nm='하리-서검(보조)',psnr_rute_sctn_nm='하리-미법')
    ends=route_endpoints(row)
    assert (ends.departure,ends.arrival,ends.calls_raw,ends.segment_name,ends.scope)==('하리','서검','미법','하리-미법','whole_route')
    assert route_endpoints(feature('piltg_rute_l')).departure is None
    with pytest.raises(SchemaError): route_endpoints(feature('pssh_p'))


def test_name_region_ambiguity_and_identity():
    row=feature(strpnt_nm=' 하리 ',dstntn_nm='서검')
    ports=[PortReference('tago','SEA001','하리','28'),PortReference('other','SEA001','하리','46'),PortReference('tago','SEA002','서검','28')]
    result=map_route(row,ports=ports)
    assert result.departure.status=='ambiguous' and len(result.ports)==3
    assert result.arrival.status=='unmatched' and result.arrival.port is None
    result=map_route(row,ports=ports,departure_region='28',arrival_region='28')
    assert result.departure.port.key==('tago','SEA001') and result.arrival.status=='matched'
    assert map_route(row,ports=ports,departure_region='99').departure.candidates==()
    with pytest.raises(SchemaError): map_route(row,ports=ports+[ports[0]])
    with pytest.raises(SchemaError): map_route(row,ports=ports,endpoint_kind='bad')
    assert map_route(feature(strpnt_nm='하리항'),ports=ports).departure.status=='unmatched'


def test_missing_endpoints_and_versioned_external_augmentation():
    row=feature('piltg_rute_l')
    port=PortReference('tago','SEA001','하리','28')
    assert map_route(row,ports=[port]).departure.status=='missing_endpoints'
    result=map_route(row,ports=[port],crosswalk=[crosswalk(row)])
    assert result.departure.port==port and result.departure.raw_name is None
    assert result.departure.evidence[-1]=='하리' and result.arrival.status=='missing_endpoints'
    assert result.endpoints.departure is None
    assert map_route(row,ports=[port],crosswalk=[crosswalk(row,record_id='other')]).departure.port is None


@pytest.mark.parametrize('change',[{'history_date':'2020-01-01'},{'source_sha256':'b'*64}, {'role':'call'},
    {'evidence_url':'file:///tmp/no'},{'evidence_record':''},{'revision':''},{'target_port_id':'unknown'},
    {'region':'46'}])
def test_invalid_or_stale_crosswalk(change):
    row=feature(strpnt_nm='하리')
    with pytest.raises(SchemaError):
        map_route(row,ports=[PortReference('tago','SEA001','하리','28')],crosswalk=[crosswalk(row,**change)])


def test_crosswalk_conflict_role_duplicate():
    row=feature(strpnt_nm='다른항')
    port=PortReference('tago','SEA001','하리')
    with pytest.raises(SchemaError): map_route(row,ports=[port],crosswalk=[crosswalk(row)])
    row=feature('piltg_rute_l')
    entry=crosswalk(row)
    with pytest.raises(SchemaError): map_route(row,ports=[port],crosswalk=[entry,entry])
    with pytest.raises(SchemaError): map_route(row,ports=[replace(port,kind='terminal',kind_evidence='review1')],crosswalk=[entry])


def test_pier_details_keep_raw_coordinates_and_year():
    row=feature('pssh_p',pssh_id='20150001',pssh_trml_nm='터미널',fcl_raddr='인천',pssh_tno='032001',
                area_sclas_cd='2811000000',invs_yr='2014',x_crdn=126.5,y_crdn=37.5)
    port=ports_from_features([row])[0]
    assert port.key==('vadahub:pssh_p','20150001') and port.kind=='facility'
    assert port.telephone=='032001' and port.source_year=='2014'
    assert port.latitude is None and port.feature.attributes['x_crdn']==126.5
    result=map_route(feature(strpnt_nm='터미널'),ports=[port],departure_region=port.region,endpoint_kind='pier')
    assert result.departure.status=='unmatched' and result.departure.candidates==(port,)
    with pytest.raises(SchemaError): replace(port,kind='pier')
    for rows in ([row,row],[feature()],[feature('pssh_p')]):
        with pytest.raises(SchemaError): ports_from_features(rows)


def test_transport_export_adapter():
    item=dict(natural_key='tago:SEA001',source='tago',port_id='SEA001',name='하리',
              latitude=37.0,longitude=126.0,location_source='survey',
              admin={'legal_dong_code':'2811000000','road_address':'인천'})
    port=port_from_transport(item,collected_at=datetime.now(timezone.utc),source_url='https://example.org/export')
    assert port.key==('tago','SEA001') and port.region=='2811000000' and port.address=='인천'
    assert port_from_transport(item|{'admin':None,'latitude':None,'longitude':None},
                              collected_at=datetime.now(timezone.utc),source_url='https://example.org').region is None
    for change in ({'natural_key':'wrong'},{'admin':[]},{'name':123}):
        with pytest.raises(SchemaError): port_from_transport(item|change,collected_at=datetime.now(timezone.utc),source_url='https://example.org')
    assert port_from_transport(item|{'location_source':'data_go_kr_port_guideline'},
        collected_at=datetime.now(timezone.utc),source_url='https://example.org').latitude is None
    unknown=port_from_transport(item|{'location_source':None,'admin':None},
        collected_at=datetime.now(timezone.utc),source_url='https://example.org')
    assert unknown.key==('tago','SEA001') and unknown.latitude is None and unknown.longitude is None


@pytest.mark.parametrize('change',[{'name':''},{'kind':'bad'},{'latitude':37},
    {'latitude':95,'longitude':126,'location_source':'survey'},
    {'latitude':float('nan'),'longitude':126,'location_source':'survey'},
    {'latitude':37,'longitude':126},{'latitude':True,'longitude':126,'location_source':'survey'}])
def test_invalid_port(change):
    with pytest.raises(SchemaError): PortReference(**(dict(source='tago',port_id='001',name='하리')|change))
