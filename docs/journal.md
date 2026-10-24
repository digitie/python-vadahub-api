# 작업 기록

## 2026-10-24 KST — T007A2 공개 웹 질의

- T007A 최종 리뷰2/live/CI와 머지 `0f76224`를 확인한 뒤 분기했다.
- 66개 안내의 backing resource 65개(한 안내는 연결자료0)를 실제 Chromium으로 조사했다.
- UI DataTables의 필수 정렬 파라미터, setRecordsTotal/recordsFiltered, camelCase JSON과
  snake_case schema를 확인해 bounded 페이지/필터/정렬 및 정확 label 연결을 구현했다.
- API140/142의 원 catalog meta와 backing meta를 별도로 보존하고 공간 layer에 기존 ZIP/GDAL을 연결했다.
- A의 공백상태/schema전단사 P2와 B의 API SHP 공개정책 P2 수정 후 `8939481` 코드 차단 없음.
- Chromium66안내 점검은 조회성공49/권한제한12/grid미제공3/139통신실패1/연결0안내1이다.
  139는 T007A2E 미완료로 남긴다. 실제API144 ZIP119행 중4invalid 기본거부/preserve 보존확인,
  unit250/94.30%, GDALlive·구현CI 통과. 개별 원천 실패를 전수 조회성공으로 표시하지 않는다.

## 2026-10-24 KST — T007A 공개 안내·자료실

- T006 최종 리뷰2/live2/CI와 머지 `0a1a53a` 확인 후 분기했다.
- OpenAPI 원40/분석25/지도1, 문서451/통계73 목록을 Chromium으로 조사했다.
  분석 안내에 동일 meta/history의 서로 다른 API ID가 있어 식별을 보강했다.
- PDF 미리보기와 다운로드 허용을 분리하고 통계 sample JSON은 partial snapshot으로 제공한다.
- 연안기본조사 ZIP 공개 버튼과 파일 내부 XLSX 폴더를 확인해 안전한 디렉터리 ZIP 검증과
  LibraryArchiveReceipt·기존 immutable store 통합을 구현했다. PRIVATE resource는 거부한다.
- B의 PDF URL 외부 origin P1 수정 후 `6995005` 리뷰2 통과. unit219/94.51%,
  실제 5종 목록/PDF/통계216행/ZIP12멤버/보관live1(skip0), 구현CI 통과.
  66개 API 안내의 실제 backing resource 전수 조사를 후속 T007A2에 반영했다.

## 2026-10-24 KST — T006 원문 보관

- T005 PR #5 리뷰2/live/최종CI와 머지 `7efc1a4`를 확인하고 분기했다.
- scope+SHA immutable 디렉터리, 멤버 payload 지문, filelock 프로세스 잠금,
  stage 검증→object 원자 공개→manifest 원자 교체, 기존 버전 보존과 고아 복구를 구현했다.
- S3는 필수 범위가 아니며 자격증명/버킷을 탐색하거나 미검증 adapter를 추가하지 않는다.
- A의 기존 원문/receipt 동시 누락 복구 P2 수정 후 `4587d74` 리뷰2 차단 해제.
  unit190/94.80%, 새ZIP live1·보관857행/멱등/고아복구live1·구현CI 통과.

## 2026-10-24 KST — T005 매핑

- T004 리뷰2/live5/최종CI 후 PR #4 머지 `467208d`를 확인하고 새 브랜치를 만들었다.
- transport DTO adapter, source+port_id 참조, pssh_p 시설 상세·원문·조사연도,
  전체항로/segment 분리, 지역+이름 유일성 및 버전고정 crosswalk를 구현했다.
- 원천 도선 출도착지 결측과 여객터미널 원격 미제공(T005E)은 해결된 것으로 표시하지 않는다.
- A 시설역할·B nullable좌표출처 P2 수정 후 최종 `59b4a4c` 리뷰2 차단 없음.
  unit172/94.80%, 새 ZIP live1 및 동일원문 최종 GDAL/매핑 live2 통과.

## 2026-10-24 KST — T004 GDAL

- T003 PR #3의 리뷰2·live4·최종 CI와 머지 `d342204`를 확인한 뒤 분기했다.
- GDAL Python binding 전용 worker, ZIP 검증, CP949 TXT 정확 필드명 연결, 원문 WKB,
  nullable CRS와 근거 있는 변환, 날짜/코드 보존, async load/iter/local API를 추가했다.
- 공간 CI를 필수로 추가하고 PR의 중복 push workflow를 줄였다.
- 추가 관광자료 요구는 T007B로 task화했으며 실제 가용성 조사는 계속한다.
- A의 WGS84 범위, B의 native traceback 수명 P2를 수정하고 `e3abca4` 재리뷰2 통과.
  unit151/93.79%, 새 원문 Chromium live4→동일 SHA GDAL live1(skip0), 필수 spatial CI 통과.

## 2026-10-24 KST — T003 카탈로그·다운로드

- PR #2 머지 확인 후 `codex/t003-catalog-download`에서 구현.
- 공개 카탈로그 페이지네이션·기초 layer·상태 재조회, UI ZIP 검증/공개 및 공유 context 잠금 추가.
- 실제 SDK로 183 meta/7 layer/6 ZIP/여객터미널 미제공 확인, 초기 unit129/95.46%.
- 각 task의 독립 리뷰2·live·CI·머지 후 다음 task로 계속 진행한다.

## 2026-10-24 KST — T001 조사·문서

- 원격 저장소를 현재 빈 workspace에 clone하고 `origin/main`과 `codex/vadahub-specifications` 구성.
- KRIC/Opinet/MOIS/transport 참조 코드 및 실제 VadaHub 공개 페이지·ZIP 조사.
- 사용자 확인: ITS는 오기, VadaHub만 대상. 추가 지시: kor-travel-geo GDAL binding 활용.
- 실제 공개 ZIP 6개 확보. 여객터미널 다운로드 N, 도선 출도착지 부재, `.prj` 부재를 확인.
- 문서 [PR #1](https://github.com/digitie/python-vadahub-api/pull/1)을 `9d73701`로 머지했다.
  독립 A/B의 P2 총 3건 수정·재리뷰, live/GDAL 재검증, 최종 head CI를 통과했다.

## 2026-10-24 KST — T002 async 기반

- T001 머지 main에서 `codex/t002-async-foundation` 분기 후 provider 구현 시작.
- KRIC src layout/패키징·문서 체계를 적용하고 Opinet token bucket 및 Chromium 생명주기를 구현.
- GDAL은 spatial extra로 분리해 core에 native ABI 의존을 강제하지 않는다.
- B가 발견한 생성/정리 정지 시 무한 대기를 유한 유예·늦은 자원 추적으로 수정했다.
- 최종 소스 `472a75a`: unit 72개/98.29%, mypy·compileall·실제 Chromium live 3개·빌드·
  별도 wheel 설치본의 실제 VadaHub 조회 통과. A/B 모두 차단 해제.
- [PR #2](https://github.com/digitie/python-vadahub-api/pull/2)의 최종 head CI/머지를 확인해 다음 task로 진행한다.
# T007B 착수 — 2026-10-24

PR #8을 dc977f1로 머지 확인한 뒤 origin/main에서 분기했다. 사용자 추가 관광자료
지시로 실제 9 ZIP을 사전 조사했다. 2897행, 해수욕장 invalid2, CRS 미상·시점·결측을
보존하는 관광 registry/요약/지연 검색과 파일 facade를 구현한다. 숙박/해안누리길 등
다운로드 제한 자료는 지원 목록에서 제외하며 관광 사양에 이유를 남겼다.

T007B 구현929a36b: 독립A/B 차단없음, 오프라인274/94.66%, 새9ZIP과 GDAL2897행 live2(skip0), 구현CI 전부 통과. 증빙 head 정산 후 머지한다.

## 2026-10-24 KST — T008 최종 설치본 검증

T007B PR #9를 d6ea2ea로 머지 확인 후 분기했다. wheel/sdist에 예제를 포함하고
격리 설치 검사를 CI matrix에 추가했다. Linux/WSL·Windows 설치와 단계별 live 절차,
실제 설치본 catalog→ZIP→GDAL→매핑→보관 재로딩 예제를 검증한다. 외부 미확보는 유지한다.

T008 구현6357c55: A 문서P2 수정·재리뷰2 차단없음, unit274/94.66%,
완전격리 wheel의 실제6ZIP857행/관광529행/API124필터·별도관광예제·Windows공개페이지 통과.
새wheel SHA0124f6d…를 증빙했다. 최종증빙head CI·리뷰 정산 뒤 PR #10을 머지한다.
