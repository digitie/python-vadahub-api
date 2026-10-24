# 남은 원천 보완 사양 검증

2026-10-24 KST. provider는9359896과 동일하며 문서 사양만 추가했다.
사양 source b30e3cc, B P2의 원천별 고정origin·redirect/context/취소 정책을 구체화했다.
CSV strict 디코딩은 stdlib, native WKT 해석은 OGR이라는 경계와 양끝 포함7일을 명시했다.

- Windows Python3.14.3/Chromium149: `test_live_files.py --run-live`,
  신규 `artifacts/remaining-spec-live`에 실제4meta/7layer/6ZIP, 터미널downloadN/버튼0;
  1 passed/skip0/31.96초.
- 동일 원문 WSL Python3.14.4/GDAL3.12.2 `test_live_spatial.py --run-live`:
  6ZIP857행, SHA/CRS 미상 대조, 1 passed/skip0/1.84초.
- A의 독립 실제 공개 Chromium 조사: 공식 터미널 CSV13811bytes/76행/WKT,
  KHOA 도선SHP31272bytes/16행/출도착지없음, 원문이 참조하는 항행통보3건 좌표만 확인.
  transport에는 VadaHub record/version과 연결하는 검토된 실 crosswalk가 없다.
- 실제 API139 gid 한정 DataTables는45.25초 NetworkError. schema/샘플 성공과 구분했다.
- 공개 aipast의 관측 JS가 쓰는 날짜·격자 통계는 실제 height1.6/period10.2 각각약3초.
  2018-06-10 GR3_F4J12_H 응답이며 원행 값/조회 성공과 별도 집계했다.
- [첫 사양CI](https://github.com/digitie/python-vadahub-api/actions/runs/40067465299)는
  core3.11~3.14/build/격리wheel/typecheck/필수GDAL spatial 및 docs 전부 통과.

[sanitized receipt](remaining-source-spec-receipt.json)에 실제원천URL/이력/해시/행수·통신결과를
연결했다. 원본CSV/SHP/HTML/브라우저상태는 커밋하지 않는다. A의 첫 사양검토는 P0/P1/P2없음,
B의 P2 수정 재리뷰와 최종head CI 후 머지한다. 미확보 도선 identity/원터미널SHP/일반grid는
성공으로 표시하지 않는다. 이 사양 머지 전 새 provider 메서드 구현을 시작하지 않는다.
