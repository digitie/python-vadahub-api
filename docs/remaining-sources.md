# 남은 원천 제약 재조사와 보완 사양

2026-10-24 재조사. 기존 provider 구현은9359896 기준이며 이 문서는 새 구현에 앞선 사양이다.
공개 보완 자료는 VadaHub 원문과 구분한다. 원본 다운로드/원행 조회가 실패한 사실은 유지한다.

## 실제 확인

- VadaHub meta52/layer500048은 이력2019-12-10, 실제 새 ZIP에서도 도선34행의 이름/출도착지가 없다.
- meta5055/layer501880은 PARTIAL/ALL/downloadN, 실제 SHP 버튼0. 제한을 우회하지 않는다.
- [해수부 공동활용체계 여객터미널 CSV](https://www.data.go.kr/data/15148558/fileData.do)는
  비로그인 공개 파일13811bytes/76행/CP949이며 WKT POINT·명칭·주소·조사년도2014를 포함한다.
  SHA9818019e52919af3afb4e6791c571ea48b821c4f38bbb5ce6cfc24e5d166b5c5.
  VadaHub의 공개 샘플gid10과 명칭/주소/년도/XY가 일치하나 전체 동일성을 증명하지 않았다.
  이 CSV를 VadaHub 원본SHP로 표시하지 않는다. WKT/속성XY에 CRS 근거가 없으므로 미상이다.
- [KHOA 별도 도선 SHP](https://www.data.go.kr/data/15130178/fileData.do)는31272bytes,
  실제GDAL16행/제작2024-11-30/PRJ·CPG 포함이다. VadaHub34행/제작2022-08-25와
  ID·버전이 다르고 새 SHP도 전행 이름/출도착지가 없다. PRJ를 VadaHub에 전이하지 않는다.
- VadaHub 원문 og_mtr_cn의 공식 항행통보3건을 실제 공개 조회했다. 원평항/맥전포항/돌산항
  부근의 선 신설·삭제 좌표만 있고 출도착지 이름·선착장 ID가 없어 확정 crosswalk가 아니다.
  의심스러운 통보번호 연도를 임의 수정하지 않는다. **실제 도선 확정매핑은 계속 미완료다.**
- API139 공개 schema/샘플은 응답했다. gid16301943 필터를 넣은 일반 DataTables도45초
  timeout. sampleApiList 경로는 HTML/XML 접근거부라 사용하지 않는다.
- VadaHub [인공지능 해양정보](https://vadahub.go.kr/analyze/marine/aipast/index.do)의
  공개 JS aiModelPastCont.js가 사용하는 날짜·격자 통계 경로는 실제 응답했다.
  GR3_F4J12_H/2018-06-10: 파고1.6/주기10.2, 각각약3초. 시간18의 schema샘플 파고1.351과
  값이 다르며 시간별 원행과 다른 날짜별 웹 통계다. 집계식/단위는 원문 UI 근거 없이 보장하지 않는다.

## T007A2E1 — 3분 격자 파랑 웹 통계

3분은 공간 격자 해상도다. 원행 API의 응답 동등성이나 실시간 자료를 뜻하지 않는다.
`VadaHubClient.get_wave3min_statistics(grid_code,start_date,end_date,measure='height')`를 제공한다.
date 인자(날짜)·양끝 포함 최대7개 날짜·격자1개·GR3 ASCII 식별자만 받는다.
datetime은 date로 묵시 변환하지 않는다.
measure는height/period만 허용하며 table/URL/SQL/임의 파라미터를 받지 않는다.

1. 실제 API139 안내와 연결자료의 OPEN/ALL/비마스킹 상태를 재확인한다.
2. 공개 aipast 화면의 제목/필수영역을 검증하고 동일 Chromium 세션에서 POST
   `/user/aiModel/selectGridStatsPastWv.do`를 호출한다.
3. 고정 tableNm=WV_3MIN,ogType=grid_3_step_a,type=wvhgh 또는pd,
   gridNo=격자코드,startDate/endDate=YYYYMMDD만 전송한다. 기존 limiter/timeout/JSON2MiB를 적용한다.
4. layerStatsWv의 gridCd/analsYmd/측정값을 검증하고 원문 scalar 속성을 immutable하게 보존한다.
   유한수/nullable 값만 허용한다. 다른 격자·범위 밖/중복 날짜·7일 초과 행은 schema 오류다.
5. typed WaveStatistics 결과에 원 resource/API ID·질의기간/측정종류·출처URL·수집시점·원행을 제공한다.
   비어 있는 정상 통계는 빈 tuple로 보존한다. 누락 날짜를0으로 채우거나 전체 커버리지를 보장하지 않는다.

성공 시 API139의 **웹 통계 지원**을 별도 표기한다. 일반 query_table timeout 제약은 남기고
기존49건 원행 조회 성공 집계에 통계 성공을 더하지 않는다. 네트워크 실패 시 자동 fallback하지 않는다.
unit은 입력/공개상태/잘못된 응답·취소를 검증하고 live는 두 측정종류·기간·실제값 및 오류 전파를 확인한다.

## T005E1 — 공식 터미널 보완 파일

원본 VadaHub download 계약을 바꾸지 않고 공식15148558 파일을 명시적으로 선택하는 보완 API를 둔다.
브라우저·출처/버전·파일 receipt는 VadaHub와 분리한다. 공공데이터포털의 실제 공개 다운로드 버튼만
사용하며 인증 API·로그인·CAPTCHA·비공개 경로를 사용하지 않는다. 공개 보완원천 사용 선호를
사용자에게 물었고, 구현 시 답변을 반영한다.

전용 `OfficialTerminalClient`와 원천별 고정 origin 세션을 사용한다. 기존 VadaHub 세션의
허용범위를 넓히지 않는다. 보완 세션은 `https://www.data.go.kr`만 허용하고 호출자가 origin이나
임의 URL을 지정할 수 없다. 시작 페이지는15148558/fileData.do로 고정하며 실제 버튼에서
관측한 `/cmm/cmm/fileDownload.do`와 첨부ID/파일순번/자료명을 대조한다. download 이벤트의
URL·redirect 각 hop을 검사하며 다른 origin으로의 이동은 거부한다. CDP의 서비스워커 우회와
소유 page/session 정리를 유지한다. 주입 context는 닫지 않고 자체 생성 context만 종료한다.
클라이언트는 기존 공유 limiter를 받을 수 있으며 페이지 이동부터 다운로드·검증까지 전체
operation timeout을 적용한다. 취소는 수신 download/임시 파일·worker 정리를 기다리고,
정리 실패/시간 초과 시 SDK의 유한 cleanup 유예·재사용 불가 정책을 유지한다.
기존 파일을 덮어쓰지 않고 검증/정리를 마친 파일만 원자 공개한다. CSV 읽기 실패나 접근거부는
정상 빈 결과로 바꾸지 않는다. 두 원천을 같은 외부 context에 주입해도 페이지별 origin 정책과
공유 context lock을 보존하는 회귀를 검증한다.

고정 공식 dataset의 페이지/첨부 identity를 검증해 호출자 지정 신규 경로에 원자 저장한다.
CSV는16MiB 상한·CP949 strict·고정 필드·고유 문자열 ID·행상한으로 검증한다. 원문은 그대로
보존하며 임의 형식 변환한 파일을 원본SHP라고 하지 않는다. 헤더/파일/리다이렉트 변경은 명시적 오류다.
전용 typed receipt에 source=data.go.kr:15148558,source_url,수집시점,SHA,bytes,local_path를 둔다.
CSV의 CP949 strict 디코딩·필드 읽기는 stdlib csv, WKT 해석은 GDAL OGR binding으로 수행한다.
`OfficialTerminalClient.load_file`/bounded `iter_file`은 같은 worker에서 native geometry를 생성·해제하고
복사한 WKB/속성만 반환한다. 취소는 worker 종료를 기다린다.

typed 터미널에는 source/record ID·nullable 명칭/주소·조사년도·원문속성·WKB·geometry_valid,
CRS 근거·SHA/수집시점을 제공한다. 전화·경위도·현재영업 정보는 만들어내지 않는다.
PortReference 변환 시 source/port_id와 공식 자료의 terminal 역할 근거를 보존한다.
CSV76행 제공은 도선 출도착지 근거 확보와 별개이며 자동 실매핑 성공으로 보고하지 않는다.

## 실행 순서와 완료 기준

이 문서 PR의 독립 리뷰2·실제원천/GDAL/공개기능·CI 후 머지한다. 다음은
T007A2E1(기존 VadaHub 경로) → T005E1(명시 공식 보완파일) 각각 독립 PR·2리뷰·live·CI·머지다.
도선 crosswalk 및 VadaHub 터미널 원본SHP의 미확보는 별도로 남긴다. 확보되지 않은 요구를
task 이름 변경이나 보완 통계/CSV로 완료 처리하지 않는다.
