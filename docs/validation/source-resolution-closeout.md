# 2026-10-25 구현 머지 정산 검증

PR #19 소스 `c185a32707960e485d933424f01bed3efbad6d7a`.
기준 main29e8bd80(PR #18)에서 문서만 변경했다. runtime은 구현9cf979c와 동일하다.
PR #16/17/18의 실제 머지를 조회하고 tasks-done/resume에 해당 SHA를 기록했다.

2026-10-25 18:16~18:18 KST Windows Python3.14.3/Chrome156.0.8078.47/PW1.64.1,
WSL Python3.14.4/GDAL3.12.2에서 새 원문 경로를 사용했다.

- 실제 Chromium **3 passed/81.78초/skip0**: 새공식CSV340·catalog183/7layer/6ZIP 및
  원터미널미제공·API139 시각별2시각/2격자/빈결과. 기준시각1.351/132.001/12.2 확인.
- 동일bytes GDAL **2 passed/2.56초/skip0**: 공간857행·도선34중1검토매핑/33미확정,
  시설340·이름/주소/출처·좌표None·원문결측/flag·원자보관/멱등/복구 통과.
- 원문해시·시점·공식첨부·두시설/crosswalk/실제시각값은
  [sanitized receipt](source-resolution-closeout-receipt.json)에 기록했다.
- 문서링크/branch diff 검사 통과. 코드/테스트/예제/도구/빌드 설정은변경하지않았다.
  구현단계의unit504/95.81%·격리wheel58exports/별도실제매핑 증빙도동일runtime에적용된다.
- 독립 A/B의 c185a32 검토 모두 P0/P1/P2 없음. 실제PR18머지·완료/미해결집계·코드동일성확인.
  B의 비차단 제안에 따라 일반표49 resource 성공의 출처를T007A2로명시했다.
- [소스CI](https://github.com/digitie/python-vadahub-api/actions/runs/40179953393)와별도docs
  전부7개통과. 증빙만추가한최종head도A/B·코드동일성·CI를확인한후머지한다.

실행 환경변수는 VADAHUB_PIER_ARTIFACTS=artifacts/source-closeout-pier,
VADAHUB_LIVE_ARTIFACTS/VADAHUB_LIVE_ARCHIVES=artifacts/source-closeout-vadahub,
VADAHUB_HOURLY_ARTIFACTS=artifacts/source-closeout-hourly다.
`tests/test_live_pier_download.py tests/test_live_files.py tests/test_live_wave_hourly.py --run-live -q -s`
이후 `tests/test_live_reviewed_mapping.py tests/test_live_spatial.py --run-live -q -s`를실행했다.
키·로그인·제한우회는없었다. rawCSV/ZIP/HTML/쿠키는커밋하지않았다.

두보완구현은머지완료이며일반API139 DataTables13필드전체·나머지33도선·원터미널SHP를
완료했다고표시하지않는다. 후속진행조건은공식공개근거의새확보다.
