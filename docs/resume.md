# 재개 지점

T003 [PR #3](https://github.com/digitie/python-vadahub-api/pull/3)은 `d342204`로 머지했다.
최종 구현 `6fe5e34`에서 독립 리뷰 A/B 차단 없음, unit132/96.49%, live4(skip0),
증빙 head `8a828cd`의 CI 전부 통과를 확인했다.

T004 PR #4를 `467208d`로 머지했다. 최종 구현 `e3abca4`, 증빙 `60961fc`에서
리뷰2·unit151/93.79%·새 ZIP live4+GDAL live1·CI를 통과했다.
T005 PR #5를 `7efc1a4`로 머지했다. 구현 `59b4a4c`에서 리뷰2·unit172/94.80%·live3,
증빙 `eaef6ca` 최종CI 통과를 확인했다.
T006 PR #6을 `0a1a53a`로 머지했다. 구현 `4587d74` 리뷰2·unit190/94.80%·live2,
증빙 `cb8064f`의 최종 CI 통과를 확인했다.
T007A PR #7을 `0f76224`로 머지했다. 최종 구현 `6995005` 리뷰2·unit219/94.51%·live1,
증빙 `1fffbf4` 최종CI 통과를 확인했다.
T007A2 PR #8을 `dc977f1`로 머지했다. 최종구현8939481·증빙7e1063c,
독립리뷰2·unit250/94.30%·live2(skip0)·최종CI7개 통과. 조회성공49건이며
API139 통신실패는 T007A2E 외부제약/미완료로 남긴다.
T007B PR #9를 `d6ea2ea`로 머지했다. 소스929a36b·증빙ac4840a에서
리뷰2·unit274/94.66%·새9ZIP/GDAL2897행 live2(skip0)·최종CI7개 통과.
현재 `codex/t008-final-acceptance`에서 clean wheel 설치·최종 소비자 검증을 진행한다.
구현6357c55의 리뷰2 차단없음, unit274/94.66%, Windows core/완전격리 WSL wheel설치,
실제6ZIP857행+관광529행+API124필터 및 관광예제, 구현CI 전부 통과했다.
최종 증빙 head 정산·CI 후 PR #10을 머지하고 완료 문서에 실제 merge SHA를 기록한다.
T005E 외부 제약은 미해결 유지한다.

추가 관광자료 요청은 T007B에 반영했다. 해수욕장·전망대·체험마을·낚시·마리나는
실제 버튼/ZIP/필드/시점을 조사해 제공한다. metadata Y만으로 가용 판정하지 않는다.

범위는 VadaHub만(ITS 오기 확인). API 키 없음. GDAL Python binding 필수.
여객터미널 원격 SHP 미제공·도선 출도착지 부재·CRS 부재를 숨기지 않는다.
