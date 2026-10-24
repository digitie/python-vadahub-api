# 항로와 선착장 매핑

`route_endpoints(feature)`는 여객항로의 `strpnt_nm`, `dstntn_nm`, `prtcl_nm`을 읽으며
`psnr_rute_sctn_nm`은 별도의 segment 이름이다. 구간명을 하이픈으로 분할하거나 선의
방향을 출도착 방향으로 간주하지 않는다. 도선은 현재 출도착지 필드가 없어 결측이다.

`ports_from_features(pssh_rows)`는 관광지정보 여객선 109개 시설의 원천 ID·이름·주소·전화·
조사연도·원본 feature를 제공한다. 2014년 조사자료이며 여객터미널 원격 자료의 대체물이 아니다.
속성 XY는 CRS 미상이라 경위도로 지정하지 않는다. geometry/WKB는 원본 feature에서 확인한다.

```python
from vadahub import map_route, ports_from_features

piers = ports_from_features(pssh_rows)
result = map_route(route_feature, ports=piers, endpoint_kind='pier')
print(result.departure.status, result.arrival.status)
for port in result.ports:
    print(port.source, port.port_id, port.name, port.address, port.telephone, port.source_year)
```

transport ferry-ports-v1 개별 DTO는 `port_from_transport(dto,collected_at=...,source_url=...)`
로 변환한다. source와 port_id를 별도로 보존하고 natural_key도 대조한다. transport 내부
인증·snapshot pagination은 소비자가 처리한다. SDK는 DB나 비밀값을 탐색하지 않는다.
export의 `admin.legal_dong_code`를 지역으로 사용하며 source 날짜/주소/좌표 출처를 보존한다.
guideline 좌표는 승선점으로 사용하지 않는다. 실제 transport export 수신 검증은 본 작업의
live 범위에 없으며 계약 fixture의 코드가 실제 운영 항구 코드라고 주장하지 않는다.

지역과 이름이 동일한 유일 후보만 `matched`다. `departure_region`/`arrival_region`은 호출자가
근거를 확인한 동일 코드 체계 값이어야 한다. 지역이 없으면 이름이 하나여도 후보만 제공한다.
다중 후보는 `ambiguous`, 후보 없는/미확정 이름은 `unmatched`, 원문 이름 부재는
`missing_endpoints`다. 이름의 trim/NFC 외에는 `항`·`도`·`선착장` 접미사를 삭제하지 않는다.
기본 endpoint_kind는 transport용 `port`다. pssh_p는 역할이 미확정인 `facility`이며
이름/지역 일치 시에도 후보만 제공한다. 이름 접미사로 역할을 추정하지 않는다.
물리 선착장 `pier`·터미널 `terminal` 참조를 직접 구성할 때는 검토한 `kind_evidence`를
필수로 제공해야 한다. 이 근거 없이 pssh_p를 승선 선착장으로 확정하지 않는다.
transport DTO의 좌표 출처가 None이면 좌표만 None으로 두고 항구 코드/이름을 보존한다.

검토된 외부 `EndpointCrosswalk`는 meta/history/layer/record/SHA와 departure/arrival 역할,
endpoint_name, target_source/target_port_id, evidence_url/evidence_record/revision을 요구한다.
다른 레코드의 항목은 무시하고 동일 레코드의 낡은 버전·역할 중복·원문 이름 충돌·대상 부재·
대상 역할/지역 충돌은 오류다. 출도착지가 없는 도선도 명시적 검토 근거가 있을 때만 연결한다.
원문 endpoint 결측은 그대로 보존하고 보강 이름은 match.evidence에 별도로 노출한다.

T005E는 여전히 미해결이다. 공개 도선 원문에 없는 출도착지/검토된 실 crosswalk와
미제공 여객터미널 원격 SHP가 확보되어야 실제 도선 연결 완료로 판정할 수 있다.
