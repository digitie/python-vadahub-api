# 재개 지점

T001 문서 PR #1은 `9d73701`로 머지했다. T002 브랜치 `codex/t002-async-foundation`에서
패키지 기초·async Chromium session·공유 제한·예외·CI를 구현했다.
현재 unit 72개/98.29%, 타입·컴파일·빌드·설치본의 실제 VadaHub 조회와
실제 Chromium live 3개를 통과했다. 두 독립 리뷰도 최종 소스 `472a75a`에서 차단을 해제했다.
[PR #2](https://github.com/digitie/python-vadahub-api/pull/2)의 최종 CI·머지 여부를 확인한다.
머지되었다면 T002를 tasks-done으로 옮기고 새 main 기준으로 T003을 시작한다.
다음은 T003 카탈로그·기초자료 발견·공개 UI 다운로드이며 T002 머지 전 구현하지 않는다.

범위는 VadaHub만(ITS 오기 확인). API 키 없음. GDAL Python binding 필수.
여객터미널 원격 SHP 미제공·도선 출도착지 부재·CRS 부재를 숨기지 않는다.
