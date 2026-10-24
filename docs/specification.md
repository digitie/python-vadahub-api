# 상세 사양

상태: T001 설계, 조사일 2026-10-24 KST. 현재 구현과 미래 계약은 task 상태로 구분한다.
원천 사실은 [실제 분석](source-analysis.md), 코드 재사용 근거는 [참조 분석](references.md)이다.

## 범위 결정

사용자 확인으로 `its.go.kr`은 오기이고 **VadaHub만 대상**이다. ITS 및 node-link는 제외한다.
VadaHub 공개 OpenAPI와 유사한 조회를 API 키 없이 공개 웹 기능으로 제공하고, 공개 파일의
다운로드·버전 보관·SHP 파싱·선착장 매핑을 구현한다. 먼저 지정 4종을 구현한다.
OpenAPI 전체 목록과 동등 기능 지원표·자료실 확장은 T007에서 실제 조사 후 추가한다.
웹에서 확인되지 않은 API 기능은 지원한다고 표시하지 않는다.

## 기능 요구사항

| ID | 요구사항 | 수용 기준 |
|---|---|---|
| F01 | 관광지정보 4개 기초자료 탐색 | meta/layer 다대일 관계·공개상태 보존, 특정 1개만 관광지정보 전체로 반환하지 않음 |
| F02 | 여객터미널 제공 | 공개 카탈로그·가용상태 제공; SHP 다운로드는 실제 허용 시만, 미제공이면 명시적 오류; 로컬 SHP 로더 제공 |
| F03 | 도선항로 SHP | 원문 34건 snapshot 검증, 익명 DBF 해석, geometry·결측 출도착지 그대로 제공 |
| F04 | 여객항로 SHP | 전체/구간 기점·기항·종점 구분, 424건 snapshot 대조 |
| F05 | 선착장 후보 제공 | 원본 ID·이름·주소·전화·좌표 근거·시점과 출처 제공 |
| F06 | 도선 출도착지 매핑 | 출도착지 없는 원본은 `missing_endpoints`; 보강 근거가 있는 경우만 매핑; 미해결/동명 후보 노출 |
| F07 | async 사용 | async with, await download/load, async iterator, I/O로 event loop 블로킹 방지 |
| F08 | 파일 관리 | 원문 immutable SHA-256 버전·크기·수집시점·출처·manifest, 실패 시 이전 버전 보존 |
| F09 | 키 없는 웹 | Chromium 공개 기능만 사용, 별도 키·로그인 요구 없음, 접근 거부를 빈 성공으로 변환하지 않음 |
| F10 | OpenAPI 유사 기능 | T007에서 서비스별 웹 대응과 미지원 사유 기록; OpenAPI와 응답 계약이 같다고 가장하지 않음 |

F02의 원천 다운로드와 F06의 도선 출도착지 보강은 외부 데이터 제약이다.
로더/상태/보강 인터페이스 구현과 실제 원천 확보를 따로 task에 기록한다.
원천이 미제공인 상태에서 4종 원격 파일 모두 제공 완료로 표시해서는 안 된다.

## 공개 Python 계약(구현 목표)

`VadaHubClient`는 키 인자를 받지 않는다. `list_datasets()`, `list_layers(dataset_id)`,
`get_availability(layer_id)`로 발견한 식별자를 사용한다. 이름 검색은 정확 일치를 기본으로 하고
공백 정규화나 별칭은 별도 규칙으로 공개한다. ID는 모두 문자열이며 조회 범위·이력키를 보존한다.

`VadaHubFileClient`는 다음 표면을 제공한다. 구현 전의 사용 예를 실행 가능 코드로 홍보하지 않는다.

| operation | 결과·계약 |
|---|---|
| `download(layer, destination)` | ZIP `ArchiveReceipt`; 페이지의 공개 버튼이 없으면 `DownloadUnavailableError` |
| `load(layer)` | 크기 상한 내 `list[SpatialFeature]`; 내부 다운로드 receipt와 계보 유지 |
| `iter(layer, batch_size=...)` | bounded async iterator; 무제한 producer thread/queue 금지 |
| `load_file(path, layer=..., source_crs=None, encoding=None)` | 로컬 ZIP을 동일 파서로 읽음; 원격 미제공 자료의 수동 확보 경로 |
| `iter_file(...)` | thread에서 bounded batch로 파싱, 조기 종료/취소 시 파일 핸들 정리 |
| `map_route(feature, ports=..., crosswalk=...)` | 출발/도착 각각의 상태·확정 선착장·후보·증거 제공 |

## 타입과 계보

- `Dataset`: meta_id, history_date(raw), title, description, source_url, availability.
- `DatasetLayer`: dataset_id, history_date, layer_id, table_name, title,
  service_auth, open_scope, grid_available, download_available. 메타 이력과 layer를 함께 식별한다.
- `ArchiveReceipt`: layer 식별, source_url, collected_at(UTC aware), sha256, byte_size,
  local_path/object_key, 원천 파일명(표시용), parser/schema version.
- `SpatialFeature`: layer_id, record_id, raw_attributes(`cN`), attributes(정식 이름),
  geometry(원문 좌표/parts), source_crs와 근거, 원문 receipt. 레코드 ID는 이름이 아닌
  layer+gid+원문 버전 문맥으로 식별한다.
- `RouteEndpoints`: 전체 항로와 segment 구분, 출발/기항/도착의 원문 문자열,
  보강 출처·revision·출처 record ID. 구간명 하이픈만으로 자동 분할하지 않는다.
- `PortReference`: source, port_id, name, province/행정코드(있는 경우), 주소·전화,
  원천 좌표/CRS·수집시점, location_source. 항구/선착장/터미널 역할도 구분한다.
- `EndpointMatch`: raw_name, status(`matched`,`ambiguous`,`unmatched`,`missing_endpoints`,
  `unverified_crs`), port(확정한 경우), candidates, method, evidence.
- `MappedRoute`: 원본 feature, endpoint별 결과, 선착장 상세 목록. 한쪽 매칭만으로 양쪽 성공이라
  표시하지 않는다. 미매핑도 원본 feature는 반환한다.

공개 타입은 typed dataclass와 `py.typed`를 제공한다. 도입 순서는 T002 모델 기초,
T004 공간 타입, T005 매핑 타입이다. 미래 타입을 빈 stub으로 미리 공개하지 않는다.

## 선착장 매핑 알고리즘

1. 원천 출도착지와 전체/구간 범위를 확인한다. 없으면 `missing_endpoints`.
2. `kor-travel-transport`의 `(source,port_id)` 및 지역+이름 유일성 원칙을 참조한다.
   transport DB ID, TAGO `SEA...`, KOMSA 코드, VadaHub ID를 서로 동일시하지 않는다.
3. 호출자가 제공한 검토된 crosswalk는 원천 layer/record ID·버전·endpoint 역할을 키로 하고
   증거 URL/record·검토 revision을 요구한다. 낡거나 범위가 다른 crosswalk는 확정에 사용하지 않는다.
4. 이름 정규화는 양끝 공백·유니코드 NFC 정도로 제한한다. `항`, `도`, `선착장`,
   `여객터미널` 접미사를 무조건 제거하면 지점이 합쳐지므로 금지한다.
5. 동일 지역·이름이 유일하고 역할이 맞으면 매칭한다. 지역이 없는 이름 일치는 후보로만 둔다.
6. 검증된 CRS의 geometry endpoint 거리로 후보를 보조할 수 있다. 원문 polyline 방향이
   출도착 순서라는 증거가 없으면 방향을 추정하지 않는다. 거리만으로 확정하지 않는다.
7. route와 port의 source/수집시점/지도 조사년도 차이를 함께 노출한다.

도선 원문에 없는 출도착지 외부 보강은 T005E 별도 작업이며, 현재 원천만으로 실제 매핑
성공률을 약속하지 않는다. 여객항로의 출도착지는 해당 자료의 매핑에만 사용한다.

## 다운로드·저장

공개 버튼 클릭으로 check→create→Innοrix→브라우저 download 이벤트를 처리한다.
세션 lock은 ZIP 저장 종료까지 유지한다. 자료명에서 로컬 경로를 만들지 않는다.
초기 기본 상한 후보는 원문 256MiB, 멤버 32개, 개별 해제 512MiB, 총 해제 1GiB,
압축비 200배다. 실제 UI 프로토콜과 큰 자료를 조사한 뒤 API 설정으로 확정한다.
Playwright download는 브라우저가 먼저 임시파일로 저장하므로 완전한 수신 전 상한 차단을
보장하지 못한다. CDP 수신 진행/크기 제한을 구현하기 전에는 메모리 무제한 load를 금지하고
전송 전체 시간·동시성·로컬 잔여공간 제한을 적용한다. 이 한계는 문서에 명시한다.

저장은 임시 파일→전송/CRC/크기/형식/hash 검증→해시 경로 원문→원자 manifest 순서다.
manifest는 dataset/history/layer→여러 SHA 버전을 기록한다. 동일 hash는 재사용하고
날짜/URL만으로 완료를 판단하지 않는다. 원문 생성 후 manifest 실패한 고아 파일은
다음 실행에서 검증 후 복구/보고한다. 삭제·보존기한은 호출자의 명시적 정책이며 기본 삭제 안 함.
원격 S3 저장은 선택 adapter로 별도 gate를 통과시킨다. 설정·비밀값을 자동 탐색하지 않는다.

## 파싱과 좌표

ZIP slip 경로(절대/상위/drive/UNC), symlink, 중복·대소문자 충돌, 암호화,
멤버/바이트/비율 제한, CRC를 먼저 확인한다. 네트워크 HTML·오류 JSON은 ZIP으로 수용하지 않는다.
자동 해제 없이 선택한 SHP/SHX/DBF/TXT를 읽는다. sidecar stem 불일치/복수 layer는
명시적으로 선택하게 하고 임의 첫 파일을 고르지 않는다.

TXT `inFieldName`과 DBF 선언을 일대일 대조한다. `c2` 같은 누락 번호를 허용하되
중복·불일치는 오류다. geometry parts·multipart·null geometry·중복 ID를 명시적으로 다룬다.
원시 코드/빈값/날짜/숫자 처리에서 0과 None을 구분하고 알 수 없는 필드를 버리지 않는다.

`.prj` 또는 호출자의 명시적 CRS와 근거가 있을 때만 WGS84로 변환한다.
GDAL OSR의 traditional GIS axis order를 명시하고 geometry 좌표는 `(lon,lat)`, 구조화 좌표는 named latitude/longitude로
제공한다. 미확인 CRS는 None이며 `(0,0)`으로 치환하지 않는다.
속성 `x_crdn,y_crdn`도 CRS 근거가 없으면 원시 속성으로 둔다.

## 실패·호출량·운영

`AccessDeniedError`, `RateLimitError`, `ProviderError`, `SchemaError`,
`ArchiveError`, `DownloadUnavailableError`, `UnknownCrsError`, `ClientClosedError`를 구분한다.
초기 호출 예산은 세션 operation 1개씩, 초당 1회·burst 1을 후보로 하고 모든 재시도에 공유한다.
사이트 자원 요청량은 operation 수와 다르므로 내부 요청까지 관찰해 별도 계측한다.
401/403/429·schema 오류는 자동 재시도하지 않는다. 임시 네트워크 오류만 제한된 backoff 후보이며
SHP 생성 재시도는 서버 상태를 바꿀 수 있어 명시적으로 통제한다.
timeout은 lock 대기·navigation·download를 포함한 operation 전체에 적용한다.
쿠키·브라우저 저장 상태·원문 HTML 전체·인증 정보는 로그/fixture에 기록하지 않는다.

## 완료 정의

각 task는 자체 PR, 독립 적대적 리뷰 2건, 최종 코드 live E2E, CI 후 머지한다.
fixture 성공은 live 성공을 대체하지 않는다. 실제 원천 제약이 남으면 해당 요구사항을
미완료로 표시하고 접근 가능한 나머지 구현을 별도 수용 기준으로 검증한다.

공간 파싱은 사용자 추가 지시에 따라 [kor-travel-geo 방식 GDAL](gdal.md)로 구현한다.
기존 pyshp 조사는 원문 구조를 확인한 사전 조사이며 production parser 결정이 아니다.
