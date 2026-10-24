# 작업 기록

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
- fixture 62개, coverage 98.39%, mypy·compileall, 실제 Chromium live 3개 통과.
- 패키지 빌드·설치본 확인, 독립 리뷰 2건·CI·머지 gate는 별도 최종 기록한다.
