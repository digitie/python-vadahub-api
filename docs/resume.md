# 재개 지점

T003 [PR #3](https://github.com/digitie/python-vadahub-api/pull/3)은 `d342204`로 머지했다.
최종 구현 `6fe5e34`에서 독립 리뷰 A/B 차단 없음, unit132/96.49%, live4(skip0),
증빙 head `8a828cd`의 CI 전부 통과를 확인했다.

현재 `codex/t004-gdal-loader`에서 GDAL 전용 worker·TXT 필드복원·WKB·근거 있는
CRS 변환과 load/iter/local API를 구현 중이다. 실제 GDAL CI를 필수 job으로 추가했다.
T004 독립 리뷰2·새 ZIP live/GDAL·최종 CI·머지 후 T005로 진행한다.

추가 관광자료 요청은 T007B에 반영했다. 해수욕장·전망대·체험마을·낚시·마리나는
실제 버튼/ZIP/필드/시점을 조사해 제공한다. metadata Y만으로 가용 판정하지 않는다.

범위는 VadaHub만(ITS 오기 확인). API 키 없음. GDAL Python binding 필수.
여객터미널 원격 SHP 미제공·도선 출도착지 부재·CRS 부재를 숨기지 않는다.
