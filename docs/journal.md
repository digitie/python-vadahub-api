# 작업 기록

## 2026-10-24 KST — T005 매핑

- T004 리뷰2/live5/최종CI 후 PR #4 머지 `467208d`를 확인하고 새 브랜치를 만들었다.
- transport DTO adapter, source+port_id 참조, pssh_p 시설 상세·원문·조사연도,
  전체항로/segment 분리, 지역+이름 유일성 및 버전고정 crosswalk를 구현했다.
- 원천 도선 출도착지 결측과 여객터미널 원격 미제공(T005E)은 해결된 것으로 표시하지 않는다.

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
