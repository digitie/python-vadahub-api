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
현재 `codex/t007a2-public-query`에서 66개 안내 연결자료 전수조사와 공개 grid 질의,
backing 공간 layer 파일 연결을 구현 중이다. T007A2 머지 후 T007B 관광 확장으로 진행한다.
T005E 외부 제약은 미해결 유지한다.

추가 관광자료 요청은 T007B에 반영했다. 해수욕장·전망대·체험마을·낚시·마리나는
실제 버튼/ZIP/필드/시점을 조사해 제공한다. metadata Y만으로 가용 판정하지 않는다.

범위는 VadaHub만(ITS 오기 확인). API 키 없음. GDAL Python binding 필수.
여객터미널 원격 SHP 미제공·도선 출도착지 부재·CRS 부재를 숨기지 않는다.
