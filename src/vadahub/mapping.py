"""출처·지역·역할과 검토 근거를 보존하는 보수적 항로 매핑."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any, Literal
import unicodedata
from urllib.parse import urlsplit

from .exceptions import SchemaError
from .models import SpatialFeature

PortKind = Literal['port', 'pier', 'terminal']
EndpointRole = Literal['departure', 'arrival']
MatchStatus = Literal['matched', 'ambiguous', 'unmatched', 'missing_endpoints']


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaError('문자열 코드/이름이 필요합니다')
    return unicodedata.normalize('NFC', value.strip()) or None


@dataclass(frozen=True, slots=True)
class PortReference:
    """transport의 source/port_id와 VadaHub의 원천 ID를 분리한 참조."""
    source: str
    port_id: str
    name: str
    region: str | None = None
    kind: PortKind = 'port'
    address: str | None = None
    telephone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_source: str | None = None
    collected_at: datetime | None = None
    source_url: str | None = None
    source_year: str | None = None
    feature: SpatialFeature | None = None

    def __post_init__(self) -> None:
        if any(not _text(value) for value in (self.source, self.port_id, self.name)):
            raise SchemaError('선착장 source/ID/이름이 필요합니다')
        if self.kind not in ('port', 'pier', 'terminal'):
            raise SchemaError('알 수 없는 선착장 역할')
        if self.collected_at is not None and (self.collected_at.tzinfo is None or self.collected_at.utcoffset() is None):
            raise SchemaError('수집시점은 timezone aware여야 합니다')
        if (self.latitude is None) != (self.longitude is None):
            raise SchemaError('좌표 쌍이 필요합니다')
        if self.latitude is not None and self.longitude is not None:
            if (not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                        for x in (self.latitude, self.longitude))
                    or not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180
                    or not _text(self.location_source)):
                raise SchemaError('좌표 범위 또는 좌표 출처 오류')

    @property
    def key(self) -> tuple[str, str]:
        return self.source, self.port_id


@dataclass(frozen=True, slots=True)
class EndpointCrosswalk:
    """특정 원문 버전·레코드·출도착 역할에 한정한 검토된 외부 근거."""
    dataset_id: str
    history_date: str
    layer_id: str
    record_id: str
    source_sha256: str
    role: EndpointRole
    endpoint_name: str
    target_source: str
    target_port_id: str
    evidence_url: str
    evidence_record: str
    revision: str
    region: str | None = None


@dataclass(frozen=True, slots=True)
class RouteEndpoints:
    """전체 항로 출도착지와 구간명·기항 원문을 분리한다."""
    departure: str | None
    arrival: str | None
    calls_raw: str | None
    route_name: str | None
    segment_name: str | None
    scope: Literal['whole_route', 'unknown']


@dataclass(frozen=True, slots=True)
class EndpointMatch:
    raw_name: str | None
    status: MatchStatus
    port: PortReference | None
    candidates: tuple[PortReference, ...]
    method: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MappedRoute:
    feature: SpatialFeature
    endpoints: RouteEndpoints
    departure: EndpointMatch
    arrival: EndpointMatch
    ports: tuple[PortReference, ...]


def route_endpoints(feature: SpatialFeature) -> RouteEndpoints:
    """여객항로 출도착지와 segment를 혼동하지 않고 도선 결측은 그대로 둔다."""
    a = feature.attributes
    if feature.layer.table_name == 'piltg_rute_l':
        return RouteEndpoints(None, None, None, _text(a.get('oc_spce_obj_krnm')), None, 'unknown')
    if feature.layer.table_name != 'psnr_rute_l':
        raise SchemaError('도선/여객항로 layer가 아닙니다')
    return RouteEndpoints(_text(a.get('strpnt_nm')), _text(a.get('dstntn_nm')), _text(a.get('prtcl_nm')),
                          _text(a.get('psnr_rute_nm')), _text(a.get('psnr_rute_sctn_nm')), 'whole_route')


def ports_from_features(features: Iterable[SpatialFeature]) -> tuple[PortReference, ...]:
    """관광지정보 pssh_p의 오래된 시설 참조. 속성 XY를 경위도로 추정하지 않는다."""
    output = []
    seen: set[tuple[str, str]] = set()
    for feature in features:
        if feature.layer.table_name != 'pssh_p':
            raise SchemaError('관광지정보 여객선 pssh_p만 지원합니다')
        a = feature.attributes
        code, name = _text(a.get('pssh_id')), _text(a.get('pssh_trml_nm'))
        if not code or not name:
            raise SchemaError('선착장 원천 ID/이름 누락')
        port = PortReference('vadahub:pssh_p', code, name, _text(a.get('area_sclas_cd')), 'pier',
                             _text(a.get('fcl_raddr')), _text(a.get('pssh_tno')),
                             collected_at=feature.source_collected_at, source_url=feature.layer.source_url,
                             source_year=_text(a.get('invs_yr')), feature=feature)
        if port.key in seen:
            raise SchemaError('선착장 원천 ID 중복')
        seen.add(port.key)
        output.append(port)
    return tuple(output)


def port_from_transport(item: Mapping[str, Any], *, collected_at: datetime,
                        source_url: str) -> PortReference:
    """kor-travel-transport ferry-ports-v1 개별 DTO adapter. 인증/DB I/O는 소비자 책임."""
    source, code, name = (_text(item.get(key)) for key in ('source', 'port_id', 'name'))
    if not source or not code or not name or item.get('natural_key') != source + ':' + code:
        raise SchemaError('transport source/port_id/natural_key 불일치')
    admin = item.get('admin')
    if admin is not None and not isinstance(admin, Mapping):
        raise SchemaError('transport admin 형식 오류')
    # admin 이름/코드 체계를 임의 변환하지 않는다. caller가 동일한 코드 체계를 사용한다.
    region = _text(admin.get('legal_dong_code')) if admin else None
    latitude, longitude = item.get('latitude'), item.get('longitude')
    if item.get('location_source') == 'data_go_kr_port_guideline':
        latitude = longitude = None
    return PortReference(source, code, name, region=region,
                         latitude=latitude, longitude=longitude,
                         location_source=_text(item.get('location_source')), collected_at=collected_at,
                         source_url=source_url,
                         address=_text(admin.get('road_address') or admin.get('parcel_address')) if admin else None)


def map_route(feature: SpatialFeature, *, ports: Iterable[PortReference],
              crosswalk: Iterable[EndpointCrosswalk] = (),
              departure_region: str | None = None, arrival_region: str | None = None,
              endpoint_kind: PortKind = 'port') -> MappedRoute:
    """지역+이름 유일성 또는 버전 고정 crosswalk로만 확정한다. 거리/접미사 추정 없음."""
    endpoints = route_endpoints(feature)
    references = tuple(ports)
    if endpoint_kind not in ('port', 'pier', 'terminal'):
        raise SchemaError('알 수 없는 endpoint 역할')
    if len({p.key for p in references}) != len(references):
        raise SchemaError('참조 source/port_id 중복')
    selected: dict[str, EndpointCrosswalk] = {}
    for entry in crosswalk:
        if (entry.dataset_id, entry.layer_id, entry.record_id) != (feature.layer.dataset_id, feature.layer.layer_id, feature.record_id):
            continue
        if entry.history_date != feature.layer.history_date or entry.source_sha256 != feature.source_sha256:
            raise SchemaError('crosswalk 원문 버전이 다릅니다')
        url = urlsplit(entry.evidence_url)
        if (entry.role not in ('departure', 'arrival') or entry.role in selected
                or not all(_text(x) for x in (entry.endpoint_name, entry.evidence_record, entry.revision))
                or url.scheme not in ('http', 'https') or not url.hostname):
            raise SchemaError('crosswalk 역할/중복/증거 오류')
        selected[entry.role] = entry

    def match(role: EndpointRole, raw: str | None, region: str | None) -> EndpointMatch:
        entry = selected.get(role)
        if entry is not None:
            if raw and _text(raw) != _text(entry.endpoint_name):
                raise SchemaError('crosswalk 출도착지와 원문 이름 충돌')
            target = next((p for p in references if p.key == (entry.target_source, entry.target_port_id)), None)
            if target is None or target.kind != endpoint_kind:
                raise SchemaError('crosswalk 대상 ID/역할이 참조에 없습니다')
            if entry.region and target.region and _text(entry.region) != _text(target.region):
                raise SchemaError('crosswalk와 대상 지역 충돌')
            if region and any(_text(value) != region for value in (entry.region, target.region) if value):
                raise SchemaError('호출자 지역과 crosswalk 대상 지역 충돌')
            return EndpointMatch(raw, 'matched', target, (target,), 'reviewed_crosswalk',
                                 (entry.evidence_url, entry.evidence_record, entry.revision, entry.endpoint_name))
        if not raw:
            return EndpointMatch(raw, 'missing_endpoints', None, (), 'source_missing')
        candidates = tuple(p for p in references if p.kind == endpoint_kind and _text(p.name) == _text(raw)
                           and (not region or _text(p.region) == _text(region)))
        if region and len(candidates) == 1:
            return EndpointMatch(raw, 'matched', candidates[0], candidates, 'unique_region_name', ('caller_region:' + region,))
        status: MatchStatus = 'ambiguous' if len(candidates) > 1 else 'unmatched'
        return EndpointMatch(raw, status, None, candidates, 'name_candidates' if candidates else 'no_candidate')

    departure = match('departure', endpoints.departure, _text(departure_region))
    arrival = match('arrival', endpoints.arrival, _text(arrival_region))
    details = {p.key: p for result in (departure, arrival) for p in result.candidates}
    return MappedRoute(feature, endpoints, departure, arrival, tuple(details.values()))
