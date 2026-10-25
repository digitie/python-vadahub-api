# 외부 원천 재조사 사양 검증

PR #16, 사양 소스 `8bd4ffa4412708d3bffeeb552b2fb9552094e43a`.
기준 main `4bc0164e48799bba5488f91ea1a06b5e2e86de78`이며 runtime/테스트/빌드 변경은 없다.
2026-10-25 KST Windows Python3.14.3/Chrome156.0.8078.47/Playwright1.64.1,
WSL Python3.14.4/GDAL3.12.2에서 실행했다.

- 새 Chromium catalog→183자료/7layer→6ZIP 및 터미널 미제공 확인: **1 passed/38.85초/skip0**.
  `VADAHUB_LIVE_ARTIFACTS=artifacts/external-resolution-spec-core`,
  `python -m pytest tests/test_live_files.py --run-live -q -s`.
- 같은 새 바이트의 GDAL 전체 읽기: **1 passed/857행/3.14초/skip0**.
  `VADAHUB_LIVE_ARCHIVES=artifacts/external-resolution-spec-core`,
  `python -m pytest tests/test_live_spatial.py --run-live -q -s`.
  도선34/여객항로424/관광38+142+109+110, 기본 CRS 미상 보존.
- 도선 새 SHA `ea587a03c876a1801ba5ce999a04d8fa41f58ada22d86ee072bbd5d8fe1d6326`.
  이전원문과 DBF header 날짜가 달라 ZIP hash가 달라졌다. 전체 ZIP 동등성을 주장하지 않는다.
- 실제 WFS 두 뷰의 시각별 값, 공식 선착장 CSV340행과 면허3버전/시 본문 조사 결과는
  [sanitized 조사](external-resolution-research.json)에 보존했다. 연구 runtime은 위 main과 동일하다.
  연구 자체는 새 SDK 메서드나 실제 SDK 매핑 완료로 집계하지 않는다.
- 독립 A/B 모두 초기2835383의 P2(문서 간 ZIP/레코드 revision 기준 모순)를 지적했다.
  8bd4ffa에서 raw/normalized속성+WKB+identity 전체에 한정된 레코드 검토로 통일했고,
  각각 독립 재리뷰 P0/P1/P2 없음, runtime diff0 확인으로 차단 해제했다.
- `git diff --check`, 문서 링크 검사를 통과했다. 초기 사양2835383의 원격 CI7개도 통과했다.
  증빙만 추가한 최종 head의 코드 동일성과 CI를 확인한 후 머지한다.

raw CSV/ZIP/HTML/쿠키는 커밋하지 않았다. API139 DataTables13필드 전체와 나머지33도선,
원터미널SHP는 미해결이며 새로운 두 기능의 구현·live 성공을 선반영하지 않는다.
