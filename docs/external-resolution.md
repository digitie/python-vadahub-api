# 외부 원천 재조사와 실제 연결 사양

2026-10-25 사용자 재개에 따른 사양이다. 기존 사양을 낮추지 않고, 실제로 확보한
시각별 값과 검토된 선착장 대응을 구현한다. 조사 중 원문은 artifacts에만 보존한다.
구현은 이 문서 PR의 독립 리뷰2·live·CI·머지 확인 뒤 시작한다.

## 새로 확인한 사실

### API139

공식 안내의 resource520360은 여전히 OPEN/ALL/gridY/maskingN이다.
공개 인공지능 해양정보 JS가 쓰는 `/imap/proxyRun.do`의 WFS capabilities에
`ofbd-DB:tb_grid_cont_wv_wvhgh_3min`, `ofbd-DB:tb_grid_cont_wv_pd_3min`이 등록됐다.
공식 DescribeFeatureType은 날짜·시각·격자와 측정값 필드를 선언한다.

실제 Chromium에서 grid `GR3_F4J12_H`, 2018-06-10/18을 한정한 GetFeature가
파고1.351·파향132.001·평균주기12.2를 반환했다. 원래 opn 샘플의 같은 시각 값과
모두 일치하며 일별 통계1.6과 다르다. 두 뷰의 geometry와 EPSG:5179도 일치했다.
이는 **시각별 AI 재분석 값의 투영**이며 원시 관측이나 일별 집계가 아니다.

반면 일반 DataTables는 UI와 같은4괄호/regex 필터·단일255초 예산 조사에서도
조사 전체127.79초에 NetworkError였다. 서버 원인을 단정하지 않는다. SHP 공개 크기 검사는
HTTP200/`fail`이라 생성/다운로드를 진행하지 않았다. 지도 generic 클릭 경로 시험은
JSON 대신 HTML이어서 채택하지 않는다. 임의 maxLength·숨은 CSV·권한 변경은 사용하지 않는다.

WFS의 필드는 원래 opn13필드 전체가 아니다. `gid`, `lo/la`, `wvlen`, 생성자/생성시점은
만들거나 샘플로 채우지 않는다. WFS FID를 opn gid라고 부르지 않는다.
기존 query_table의 성공 집계와 WFS 시각별 조회 지원 집계는 구분한다.

### 도선과 선착장

공개 지도 `_allObjs`의 piltg_rute_l은 meta52/hist2019-12-10/layer500048/publicCode0000000001과
연결된다. 같은 WFS의34행은 기존 SHP34행과 gid·제작일20220825·ENC·객체번호·NTM·전체
vertex가 일치했다. 좌표 차이 최대5.13e-9m는 JSON 소수 직렬화 차이다.
같은 공식 레이어의 CRS가 EPSG:5179임을 확인했으며 다른 파일의 PRJ를 전이한 것이 아니다.
개별 ZIP의 기본 CRS 미상은 유지하고, 이 근거를 명시한 caller override만 사용한다.

추가 공식 자료는 다음과 같다.

| 자료 | 실제 확보 | 의미와 한계 |
|---|---|---|
| [해경 유도선 항로15068276](https://www.data.go.kr/data/15068276/fileData.do) | 20210928/113행, 20221007/77행, 20231011/89행, 20260901/77행 | 면허의 출발·도착 이름/주소. 연도별 schema/encoding/행수가 다르고 주소·거리 단위 모순을 보존 |
| [해경 선착장15070386](https://www.data.go.kr/data/15070386/fileData.do) | 20201020/CSV23800bytes/340행/CP949 | 선착장명·주소·DMS·원문 flag15필드. 메타의 전체행1과 실제340 불일치를 숨기지 않음 |
| 여수시 관광문화 공개 본문 | 국동~대경도/대합실 어항단지로124 및 2026지원안내의 도선3척 | 실제 비로그인 Chromium 본문. 섬 대표 관광좌표를 승선점으로 쓰지 않음 |
| 제주도 교통/주차 공식 안내·KOMSA MTIS | 도항선 이름쌍 및 공개 면허/기항지 코드 연결 | 한림/비양도는 현 MTIS 목록에 없고 주소/시점 충돌도 있어 확정하지 않음 |

gid2는 해경2021/2022/2023의 국동→경호 외동 이름·양쪽 주소가 유지되고,
2020공식 선착장 row84/85(파일 내1부터 센 행)의 외동/국동 두 주소와 정확히 일치한다.
원선 전체는495m이며 면허 거리 원문0.5와 분리 기록했다. 원선 양끝과 두 시설의 DMS
근사 위치 대조도 양쪽 후보가 유일하다. 방향은 면허의 출발/도착 필드로 정한다.
원문 vertex 순서와 최근접 거리만으로 방향/이름을 정하지 않는다.

이 여러 공식 근거를 결합한 **gid2 한 건의 검토된 역사적 시설 대응**을 구현 대상으로 한다.
원선의 이름/출도착 결측은 변경하지 않는다. 다른33행에는 같은 pair를 복제하지 않는다.
차트 경계로 잘린 선분에 전체 면허 양끝을 붙이지 않는다. 현재 운항이나 법적 유효기간을
보장하지 않는다. 실제 조사/구현/live 매핑 건수도 각각 분리한다.

## T007A2E2 — 시각별 파랑 원값 조회

`VadaHubClient.get_wave3min_hourly(grid_code, *, analysis_date: date, hour: int)`를 추가한다.
입력은 ASCII GR3 격자1개, 실제 date1개(datetime 제외), 0..21의3시간 간격 시각1개다.
임의 URL·typeName·CQL·XML·table·SQL·기간/다중격자는 받지 않는다.

1. 전체 메서드 timeout 안에서 API139와 resource520360의 현재 공개상태·원천명을 재확인한다.
2. 공개 aipast 페이지와 두 고정 WFS 타입의 공개 메타데이터를 확인한다.
3. 같은 Chromium 세션의 고정 proxy에 WFS1.1.0 GetFeature/JSON 요청을 보낸다.
   typeName은 위 두 개만, maxFeatures=2, viewparams는 anals_ymd:YYYYMMDD;anals_hhs:HH,
   CQL은 검증된 grid_cd의 단일 equality다. 쓰기 WFS는 구현하지 않는다.
4. HTTP/HTML/XML 예외,2MiB 상한, JSON/정수 count, 요청 identity, nullable 유한수,
   중복/다른 시각·격자, 두 뷰의 key/파향/원 geometry 일치를 검증한다.
   표준 XML은 외부 DTD/schemaLocation을 따라가지 않는다. 내부망 주소에 접속하지 않는다.
5. `WaveHourlyRecord`는 격자/date/hour, nullable 파고/파향/평균주기, 각 뷰의 immutable
   원문속성과 원 FID·원 feature JSON을 보존한다. 좌표를 파생하지 않는다.
   `WaveHourlySnapshot`은 resource/API139·질의·source URL/타입·UTC수집시점과 rows tuple을 둔다.
6. 두 뷰가 모두 정상0건이면 빈 tuple이다. 한쪽만 있거나 여러 후보면 schema 오류다.
   누락 시각을0으로 채우지 않고 다른 경로로 자동 fallback하지 않는다.

클라이언트 lock/limiter/외부context 소유권·취소·유한 cleanup 정책은 기존과 같다.
이 기능은 시간별 값 조회를 제공하지만 opn13필드 전체나 DataTables 응답 동등성을 뜻하지 않는다.

## T005E2 — 공식 선착장과 검토된 실제 매핑

### 공식 선착장 파일

`OfficialPierClient`는15070386의 현 공개20201020 파일만 명시적으로 선택한다.
고정 data.go.kr origin·dataset/페이지/JSON-LD·실제 공개버튼/첨부/파일명을 대조한다.
실제 dataNm에는10/20/2020이 있고 suggested filename은10_20_2020이다. 둘을 구분한다.
터미널 클라이언트와 검증/정리 공통 코드는 재사용하되 각 고정 identity를 섞지 않는다.
새 URL/파일명을 caller가 지정할 수 없다. 기존 destination은 덮어쓰지 않는다.

`download/load/iter/load_file/iter_file`과 `PierFileReceipt`를 제공한다.
16MiB/10000행/CP949 strict/15개 정확한 헤더·열수·행상한을 검증하고 원문을 보존한다.
worker·bounded batch·조기종료/취소·임시파일 정리는 기존 파일 계약과 같다.
LocalArchiveStore는 별도 official/data-go/15070386/2020-10-20 scope에 원자 보관한다.
원문해시/manifest/멱등성/복구 및 실패 시 이전 성공 보존을 검증한다.

`OfficialPier`는 source/파생 row ID·이름/주소·원 DMS/flag/원문속성·SHA/시점을 보존한다.
원천에 공식 시설 ID가 없으므로 ID는 `derived:버전:SHA:행번호`이며 정부 코드라고 부르지 않는다.
전화·현재 운항 여부를 만들지 않는다. DMS의 datum이 선언되지 않아 구조화된 경위도는None이다.
빈값과0, N과결측은 다르다. 도선기착지N/빈값과 후속 면허의 시점 불일치를 품질 근거로 보존한다.
`pier_to_port`는 공식 선착장 역할 근거와(source, port_id)를 유지하는 PortReference를 반환한다.
TAGO/KOMSA 코드와 같다고 하지 않는다. transport DB·비밀값·환경을 읽지 않는다.

### 검토된 crosswalk

`reviewed_route_crosswalks(feature, *, receipt, piers)`는 검토된 gid2에만 두 EndpointCrosswalk를
반환한다. 호출자는 기존 `map_route(..., endpoint_kind='pier')`로 실제 두 선착장 정보를 얻는다.

- layer/meta/history/record·제작일·객체/ENC와 원 WKB·원문 속성·정규화 속성의 검토 fingerprint를 확인한다.
- feature와 ArchiveReceipt의 layer/SHA를 대조한다. Archive SHA가 달라도 위 레코드 전체가
  같으면 동일한 레코드 검토 revision으로 현재 Archive SHA에 연결한다. 이는 해당 레코드만의
  판정이며 다른 행·ZIP 전체 멤버의 동일성이나 검토를 주장하지 않는다. DBF 헤더 날짜 등
  ZIP 재생성 차이를 전체 파일 동등성으로 간주하지 않는다.
- pier source/date/전체 원문 SHA와 해당 row의 이름/정확 주소·파생 ID를 확인한다.
- 검토 revision/evidence URL·파일버전·해시·면허행·시설행·품질 차이를 증거에 보존한다.
- 다른33행은 빈 crosswalk로 남긴다. 검토 대상gid2의 내용/원천 버전 변경·중복 target·
  행 누락·가짜 출처는 오류이며 다른 이름/근접 시설로 대체하지 않는다.

원본 RouteEndpoints의 결측과 외부 확정 근거를 함께 제공한다. 원문 속성이나 좌표를 수정하지 않는다.
crosswalk 자체는 작은 검토 manifest로 패키지에 포함하며 CSV/ZIP/HTML 전체는 커밋하지 않는다.

## 순서와 수용 기준

1. 이 사양 PR: 독립 A/B·새 catalog/6ZIP·GDAL·새 공식파일/시각값 조사 증빙·CI 후 머지.
2. T007A2E2: 독립 PR·두 리뷰·입력/잘못된 WFS/크기/중복/취소 unit,
   실제 복수 시각/격자·두 뷰/빈 결과 및 격리 wheel live·CI 후 머지.
3. T005E2: 독립 PR·두 리뷰·기존 터미널/보관 회귀와 원문/버전/오매핑 실패 unit,
   새SHP+공식선착장CSV→GDAL→검토 crosswalk→실제 양끝 선착장·보관/재로딩·wheel live·CI 후 머지.
4. 완료/재개 문서에 실제 머지SHA·지원 범위·성공/미해결 건수와 남은 원천 제약을 정산한다.

skip/fixture는 live 성공이 아니다. 일반 DataTables 실패와 원본 터미널SHP 미제공은 보완 기능으로
숨기지 않는다. gid2의 실제 구현/live를 통과하기 전에는 실제 매핑 성공으로 집계하지 않는다.
