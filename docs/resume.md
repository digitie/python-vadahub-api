# 재개 지점

2026-10-25 사양 PR #16을 `8fddde9472205b965b230a90832351f06e2c564a`로 머지했다.
독립 A/B 재리뷰·새6ZIP/GDAL857행·최종CI7개 통과. T007A2E2 구현10a2453의 리뷰2/live2/wheel/CI7개 통과. PR #17 최종증빙head 검증·머지 대기다.

2026-10-25 사용자 재개: [외부 원천 재조사/실제 연결 사양](external-resolution.md)의
문서 PR을 준비한다. 공개WFS에서API139의시각별파고/파향/주기를실제조회했고,
공식선착장340행+면허3버전+지도SHP동일성으로gid2한건의검토후보를확보했다.
아직구현/live매핑0건이며기존원천제약완료를선반영하지않는다.
사양머지 → T007A2E2 → T005E2 각각리뷰2/live/CI후머지순서로진행한다.

2026-10-24 사용자 재개: [보완 사양](remaining-sources.md) PR #12를
`c376b275b7d1636af51b8967c0f0e1b8933fa09f`로 머지했다(리뷰2·새6ZIP/GDAL857행·CI7개).
T007A2E1 [파랑 웹 통계](wave-statistics.md) PR #13을37e0ced로 머지했다.
T005E1 [공식 터미널 보완 파일](terminal-supplement.md) PR #14를
`7f74917fb7d44b82096dfdbc62af694f02296654`로 머지했다. 최종소스bc14a36/증빙head0b3961a에서
독립리뷰2·unit370/95.02%·실제Win live6/GDAL live3(skip0)·격리wheel76행·최종CI7개 통과.
2026-10-24까지의 보완 구현은 모두 머지됐다. 새2026-10-25 task는 위 지점을 따른다.
남은 항목은 T005E와 T007A2E의 원천 확보 제약이다. 새 출도착지 근거·원본SHP·
일반 API139 실제 조회 성공이 확보될 때 새 사양/PR부터 재개한다.
도선 출도착지/원본터미널 SHP/일반 API139 grid 통신 제약은 해결했다고 표시하지 않는다.

**T001~T008의 가능한 구현·검증·PR 머지 완료.** 최종 구현 PR #10은
`bc92785ae688fddb7f2ecea52679a2e2b7282eaa`로 머지했다.
미완료는 [tasks](tasks.md)의 T005E(도선 원천 출도착지/여객터미널 원격SHP)와
T007A2E(API139 실제 조회 성공 확보)다. 이 자료가 제공되지 않은 상태를 완료로 바꾸지 않는다.

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
T008은 clean wheel 설치·최종 소비자 검증을 완료했다.
구현6357c55의 리뷰2 차단없음, unit274/94.66%, Windows core/완전격리 WSL wheel설치,
실제6ZIP857행+관광529행+API124필터 및 관광예제, 구현CI 전부 통과했다.
최종 증빙 head de643dc의 A/B 차단없음과 CI7개 통과 후 PR #10 머지를 확인했다.
설치/사용은 [installation](installation.md), 지원 범위는 [관광](tourism.md)과
[공개 안내](public-catalogs.md), 검증은 [T008](validation/t008.md)을 따른다.
T005E 외부 제약은 미해결 유지한다.

추가 관광자료 요청은 T007B에 반영했다. 해수욕장·전망대·체험마을·낚시·마리나는
실제 버튼/ZIP/필드/시점을 조사해 제공한다. metadata Y만으로 가용 판정하지 않는다.

범위는 VadaHub만(ITS 오기 확인). API 키 없음. GDAL Python binding 필수.
여객터미널 원격 SHP 미제공·도선 출도착지 부재·CRS 부재를 숨기지 않는다.
