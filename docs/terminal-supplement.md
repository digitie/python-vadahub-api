# 공식 여객터미널 보완 파일

`OfficialTerminalClient`는 해양수산부가 공공데이터포털15148558에 공개한 CSV를 명시적으로
선택하는 파일 클라이언트다. VadaHub `VadaHubFileClient.download`의 터미널SHP 미제공
상태를 바꾸거나 자동 fallback하지 않는다. 별도 원본/출처/버전이며 2014년 조사자료다.
VadaHub의 공개 샘플과 일부 속성을 대조했으나 전체 동일성을 증명하지 않았다.

```python
from vadahub import OfficialTerminalClient, LocalArchiveStore, TerminalFileReceipt, terminal_to_port

async def read_terminals():
    async with OfficialTerminalClient(timeout=60) as client:
        receipt = await client.download('terminal-new.csv')
        stored = await LocalArchiveStore('vadahub-store').put(receipt)
        assert isinstance(stored.receipt, TerminalFileReceipt)
        rows = await client.load_file(stored.receipt.local_path, receipt=stored.receipt)
        ports = [terminal_to_port(row) for row in rows]
        print(ports[0].source, ports[0].port_id, ports[0].kind)
```

웹 다운로드는 GDAL 없이 사용 가능하다. source는`data.go.kr:15148558`, content_date는
2014-12-31이고 collected_at은 별도 UTC 시점이다. receipt에 실제 source/download URL,
SHA256·바이트·경로를 보존한다. 고정 공개 페이지의 자료명/버전·JSON-LD 첨부와 실제 버튼 및
download URL/파일명을 대조한다. 키·로그인·인증 API·임의 URL을 받지 않는다.
실제 페이지 설명의 literal TAB은 JSON-LD에서 허용하되 URL/identity는 엄격 검사한다.

전용 세션의 origin은https://www.data.go.kr다. 기존 VadaHub 세션은 계속vadahub.go.kr만
허용하며 서로 확장하지 않는다. redirect 각hop과 서비스워커 정책·외부context 소유권·공유
context lock을 유지한다. 같은 loop의 limiter를 두 클라이언트에 명시적으로 공유할 수 있다.
다운로드/검증까지 operation timeout, 유한 cleanup 유예를 적용한다. 브라우저가 원문을
수신한 뒤16MiB 제한을 검사하므로 수신 전 디스크 상한을 보장하지 않는다.
완료된CSV를 strict 검사·원문정리한 뒤 신규 경로에 원자 공개하며 기존 파일은 덮어쓰지 않는다.
취소/오류/정리실패는 이전 성공과 원문을 훼손하지 않는다.

`load_file`/`iter_file`은 CP949를 strict 디코딩하고13개 고정 필드·문자열 고유 ID·연도를
검증한다. CSV는stdlib, WKT는GDAL OGR로 한 worker에서 처리한다. Native 객체는 worker에서
해제하고 복사한 WKB·속성만 async 경계를 넘긴다. 원문16MiB·최대10000행, 대기2batch/각4MiB
목표로 제한한다. `iter_file`의 batch_size는1~256이며 조기 종료는aclosing을 사용한다.
`load()`/`iter()`는 공개 다운로드와 임시파일 수명까지 관리한다. 원문을 영구 보관하려면
명시적인download/LocalArchiveStore를 사용한다.

PassengerTerminal은 원문속성·nullable 이름/주소/년도·WKB/geometry_valid·SHA/시점과
출처를 보존한다. WKT는2D POINT만 허용한다. null/EMPTY geometry는None이며0좌표로
채우지 않는다. 전화/경위도/현재영업을 만들지 않는다. CSV에는 CRS 선언이 없으므로
속성XY의 범위나 다른 원천 PRJ를 근거로 변환하지 않는다.
공식 receipt 없이 읽은 파일의 source는`local_csv:SHA`이며 공식 원천이라고 표시하지 않는다.

`terminal_to_port`는 공식 source와 문자열 record_id, 명칭/주소/년도·terminal 역할 근거를
보존한다. 좌표는 미확인으로 두고 출도착 이름/지역 근거 없이 도선 실매핑을 확정하지 않는다.
수동 로컬파일은 역할의 caller kind_evidence가 필수다. 이름 결측은 오류이며 가공 이름을 넣지 않는다.

LocalArchiveStore는 CSV를`objects/official/data-go/15148558/2014-12-31/SHA/source.csv`에
immutable 보관한다. CSV content_fingerprint는원문SHA다(압축멤버가 없음). `versions(receipt)`로
이 source/date scope의 버전을 조회하고 recover는 기존 manifest/sidecar/CSV를 재검증한다.
ZIP/자료실 scope와 분리하며 동일SHA는 처음 수집한 metadata를 재사용한다.
CSV 형식 손상·해시 불일치는ArchiveError로 보고하고 성공 버전을 지우지 않는다.

[실행 예제](../examples/terminal_supplement.py)와 [남은 제약](remaining-sources.md)을 함께 읽는다.
이 보완 기능이 VadaHub 원본 여객터미널SHP 확보·도선 출도착지 매핑 완료를 뜻하지 않는다.
