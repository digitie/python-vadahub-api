# 실제 제공자료 분석

조사일: **2026-10-24 KST**. API 키·로그인 없이 Playwright async Chromium으로
페이지의 공개 버튼과 페이지가 쓰는 카탈로그 요청을 확인했다. 공식 OpenAPI의 성공을
검증한 문서가 아니며 공개 웹 내부 인터페이스는 변경될 수 있다.

## 출처와 범위

- [공간 데이터 카탈로그](https://vadahub.go.kr/renew/spaceData/index.do)
- [도선항로](https://vadahub.go.kr/renew/spaceData/detail.do?metaSn=52&histDe=2019-12-10)
- [여객항로](https://vadahub.go.kr/renew/spaceData/detail.do?metaSn=63&histDe=2019-12-10)
- [관광지정보](https://vadahub.go.kr/renew/spaceData/detail.do?metaSn=3076&histDe=2019-12-10)
- [여객터미널](https://vadahub.go.kr/renew/spaceData/detail.do?metaSn=5055&histDe=2019-12-10)
- [OpenAPI 원데이터 안내](https://vadahub.go.kr/bigdata/openApiRenew/index.do),
  [분석 가공 데이터](https://vadahub.go.kr/bigdata/openApiRenew/indexAnal.do),
  [지도 데이터](https://vadahub.go.kr/bigdata/openApiRenew/indexMap.do)는 T007에서
  카탈로그와 웹 대체 가능성을 조사한다. 이름만으로 API와 웹의 동등성을 보장하지 않는다.

사용자가 `its.go.kr`은 오기이며 VadaHub만 대상임을 확인했다. ITS 및 ITS node-link는
이번 범위에서 제외한다. VadaHub 자료실은 [문서자료](https://vadahub.go.kr/renew/docData/index.do),
[통계자료](https://vadahub.go.kr/renew/statsData/index.do)를 후속 T007 조사 대상으로 둔다.

## 카탈로그·레이어

공간 카탈로그는 183개 meta를 반환했다. 최초 화면은 15개 카드만 로드하므로 그 화면만
읽으면 대상이 누락된다. 아래 숫자는 조사 snapshot이며 영구 상수가 아니다.
`histDe=2019-12-10`은 메타 이력키이며 SHP 내용의 최신 날짜가 아니다.

| metaSn·표시명 | bsisDtaSn | relateDtaNm | 하위 자료명 | 공개/다운로드 상태 |
|---|---|---|---|---|
| 52 도선항로 | 500048 | `piltg_rute_l` | 도선항로 | OPEN / ALL / Y |
| 63 여객항로 | 500059 | `psnr_rute_l` | 여객항로 | OPEN / MEMBER / Y; 공개 버튼 다운로드 성공 |
| 3076 관광지정보 | 501297 | `scene_road_p` | 경관도로 | OPEN / MEMBER / Y; 공개 버튼 다운로드 성공 |
| 3076 관광지정보 | 501298 | `trl_p` | 산책로 | OPEN / MEMBER / Y; 공개 버튼 다운로드 성공 |
| 3076 관광지정보 | 501304 | `pssh_p` | 여객선 | OPEN / MEMBER / Y; 공개 버튼 다운로드 성공 |
| 3076 관광지정보 | 501991 | `trrsrt_a` | 관광지 | OPEN / ADMIN / Y; 전체보기로 펼친 뒤 공개 다운로드 성공 |
| 5055 여객터미널 | 501880 | `psnr_trml_p` | 여객터미널 | PARTIAL / ALL / **N**, 다운로드 버튼 없음 |

`serviceAuthCd`·`opnScopeSe`·`dwldPosblYn`은 서로 다른 신호다. 메타에 MEMBER/ADMIN이
있다고 로그인 성공을 주장하지 않는다. 현재 공개 UI에서 실제 가능한 동작을 별도 기록한다.
미제공 자료는 오류로 알리고 허용되지 않은 서버 호출로 ZIP을 만들지 않는다.
관광지정보는 4개 하위 layer이며 처음 3개만 보인다. `전체보기` 버튼을 정상 클릭한다.

## 페이지가 사용하는 요청

| 요청 | 용도·관찰 계약 |
|---|---|
| POST `/renew/spaceData/list.do` | form `pageIndex,pageUnit,metaNm` 등; JSON `resultList`, `paginationInfo.totalRecordCount` |
| POST `/renew/selectMdMetaRelateList.do` | `metaSn,histDe`; top-level `resultList`, `resultListTotCnt` |
| GET `/renew/spaceData/detail.do` | 해당 meta 상세 및 기초 layer별 공개 버튼 |
| POST `/renew/gov/getBsisDataDetails.do` | `bsisDtaSn`; 최종갱신일자·갱신주기. 자료 내용의 시점으로 오해하지 않음 |
| POST `/user/meta/selectSankeyTableInfo.do` | `relateDtaNm,gubun=map`; `schemaInfo`와 샘플 `tableInfo`. 샘플을 전체 목록으로 쓰지 않음 |
| POST `/user/meta/bsisCsvDownloadCheck.do` | UI가 `bsisDtaSn,downloadType=SHP`로 검사; 관찰값 `success` |
| POST `/user/meta/metaCreateShp.do` | UI가 `bsisDtaSn,bsisDtaNm`으로 원문 생성 |
| `/user/meta/shpDownload.do` | Innorix가 초기 요청 후 offset 요청을 실행하고 브라우저 download 이벤트 발생 |

Accept가 빠지면 JSON 대신 XML이 올 수 있어 `Accept: application/json`을 명시한다.
중첩 `modelAndView`나 VO의 복사본을 재귀 순회하면 중복된다. 확인된 top-level 필드만 쓴다.
일부 오래된 JS 주석에 GeoServer WFS 다운로드가 있지만 현재 동작이 아니므로 사용하지 않는다.
Innοrix offset 인자나 임시 파일명은 공개 URL 규칙으로 일반화하지 않는다.
생성→전송 사이 세션을 유지하고 한 세션의 파일 생성은 직렬화한다.

## 실제 ZIP 확인

다음은 최초 조사에서 공개 버튼으로 실제 내려받고 pyshp로 전 행을 읽은 결과다.
ZIP hash는 **최초 수집 실행**의 값이다. 최종 재현 실행은 별도
[공개 receipt](validation/t001-public-receipt.json)에 실행 시각·코드 SHA·ZIP/member SHA를 기록한다.
서버가 매번 ZIP을 재생성하므로 member timestamp/order 차이로 ZIP hash가 달라질 수 있다.
재수집 비교에서 멤버 payload 바이트는 같고 ZIP timestamp만 바뀜을 확인했다.
원문 ZIP 식별 hash와 데이터 내용의 fingerprint를 구분한다.

| layer | 실제 bytes | 레코드 | SHP 유형 | SHA-256 |
|---|---:|---:|---|---|
| piltg_rute_l | 6,992 | 34 | PolyLine(3) | `50b858417f11eb9db857ac4a7cf87eeafb3a1c85f51d4cc5b1e2ac96aae83538` |
| psnr_rute_l | 233,748 | 424 | PolyLine(3) | `fe9698336a11dfe7f74e9ef496d40287444f459398f4419f91fe6b42ea80a2e3` |
| scene_road_p | 5,193 | 38 | Point(1) | `cf67fc94c13fd28550cb0383733a3f6d41e0f7e3e578abd95e328d70c752df7b` |
| trl_p | 12,484 | 142 | Point(1) | `6273d013d789b12047b740ebde1b759885571a0bde54cec901c595155e5f9bc5` |
| pssh_p | 12,498 | 109 | Point(1) | `0c2b2255472ce064199658afe939e84e419e90273b3ea6f424f4882b9ef4d056` |
| trrsrt_a | 298,125 | 110 | Polygon(5) | `80179117c591519626b462729f432b9b69cb8fc6aecec9e0a357e7be8b50d010` |

각 ZIP은 `.shp,.shx,.dbf,.txt`를 포함했다. `.prj`와 `.cpg`는 없다.
TXT는 CP949로 확인했다. DBF 텍스트도 CP949로 엄격 해석했고 한글을 확인했다.
원본 자료는 CP949 문자열 필드 길이 제한으로 설명이 잘릴 수 있다. 이를 라이브러리가 복원했다고
주장하지 않는다. 숫자 필드 폭/scale도 실제 DBF 선언과 TXT 설명이 다를 수 있다.

### 익명 필드 매핑

DBF 이름은 `c1..cN`이다. TXT 각 행은
`{inFieldName=c1, columnName=gid, columnDescription=..., columnType=...}` 형태다.
여객항로는 `c2`가 없으므로 순번으로 대응시키면 이후 모든 필드가 어긋난다.
TXT의 `inFieldName`을 정확히 조인하고 geometry 설명 행은 DBF 필드로 취급하지 않는다.

### 도선항로와 여객항로

`piltg_rute_l`의 이름 필드는 `oc_spce_obj_krnm`, 설명은 `piltg_rute_dc`이나
현재 34건 모두 비어 있다. 전용 출발·도착 필드도 없다. `oc_spce_obj_no`, `enc_no`,
`mfgg_ymd`, `lvl_se_cd` 등은 있으나 항구코드가 아니다. 실제 제작일은 `20220825`다.
따라서 **현재 원문만으로 도선항로의 출도착지 기반 확정 매핑은 불가능**하다.

`psnr_rute_l`에는 `psnr_rute_nm`, `strpnt_nm`(기점), `prtcl_nm`(기항지),
`dstntn_nm`(종점), `psnr_rute_sctn_nm`(항로구간명), `str_cdpnt_rute_dstc`가 있다.
한 레코드의 기점·종점은 전체 항로이고 geometry/구간명은 중간 구간일 수 있다.
예: 군산-말도 항로의 장자도-관리도 구간이다. 전체 항로 endpoints와 구간 endpoints를
구분하지 않으면 잘못된 선착장 연결이 생긴다. 거리 단위는 확인 전 원시 값으로 보존한다.

### 선착장 후보와 좌표

`pssh_p`의 `pssh_trml_nm,fcl_raddr,pssh_tno,x_crdn,y_crdn`은 여객선 시설 정보이며
선착장 후보를 제공한다. 현재 109건, 조사년도 `2014`인 값이 있어 현재 운영을 보장하지 않는다.
`psnr_trml_p`는 별도 원본이며 `dstntn_nm,psnr_trml_id,fcl_raddr,psnr_trml_tno` 등이
공개 schema에 있다. `tableInfo`는 샘플이므로 완전성 증거가 아니다.

SHP geometry는 약 80만~200만 크기의 투영 좌표이고 일부 속성 `x_crdn,y_crdn`은
126/37 같은 수치다. 범위나 형태만 보고 EPSG:5179/4326을 확정하지 않는다.
공식 CRS 근거나 `.prj`가 없으면 `source_crs=None` 및 원시 좌표를 제공한다.

## 추가 검증할 사항

T003에서 관광지 layer 전체와 변화한 공개 상태, T004에서 ZIP 제한·유효하지 않은 geometry·
TXT 중복·완전성, T005에서 도선 출도착지 외부 보강과 crosswalk 근거를 검증한다.
다른 원천을 사용하면 데이터 원본을 표시하고 VadaHub 원문에 있었다고 주장하지 않는다.
OpenAPI 전체 서비스 및 웹 대응의 지원/부분지원/미지원 목록은 T007에서 확정한다.
