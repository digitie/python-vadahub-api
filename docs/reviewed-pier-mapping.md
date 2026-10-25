# 공식 선착장과 검토된 도선 연결

`OfficialPierClient`는 해경 [선착장정보15070386](https://www.data.go.kr/data/15070386/fileData.do)의
공개20201020 CSV를 Chromium 버튼에서 수집한다. 현재 실제파일340행/23800bytes/CP949이며
포털 메타의 전체행1과 다르다. 기존 VadaHub 관광 여객선109시설·여객터미널과 다른 출처다.

```python
from vadahub import OfficialPierClient, LocalArchiveStore, pier_to_port

async def collect():
    async with OfficialPierClient(timeout=90) as client:
        receipt = await client.download('new-piers.csv')
        stored = await LocalArchiveStore('archive').put(receipt)
        rows = await client.load_file(receipt.local_path, receipt=receipt)
        for row in rows:
            print(row.name, row.address, row.raw_attributes, pier_to_port(row).key)
```

`download/load/iter/load_file/iter_file`와 async context/aclose를 지원한다.
행 iterator의 조기종료는 `contextlib.aclosing`으로 감싼다.16MiB/10000행/정확한15헤더/CP949
strict·열수·행수를 검사하고 bounded worker로 전달한다. 고정 페이지·제목/버전·JSON-LD·첨부와
버튼·suggested filename을 대조한다. dataNm의10/20/2020과 파일명의10_20_2020을 구분한다.
터미널과 같은 고정 origin·각 hop 검사·공유 limiter/context소유권·취소·유한 cleanup을 쓴다.
신규 경로만 원자 공개하며 실패·취소는 기존 파일을 덮어쓰지 않는다.

`PierFileReceipt`의 출처/버전·해시·시점/다운로드 URL을 파일 로더와 보관소가 재검증한다.
보관 scope는 `official/data-go/15070386/2020-10-20`이고 source.csv/receipt/manifest·멱등/복구는
기존 ZIP/터미널과 같다. local_file에 공식 receipt를 주지 않으면 local_csv 출처이며 공식 시설로
가장하지 않는다. 원문에 시설 고유코드가 없어 `derived:20201020:전체SHA:행번호`가 파생 키다.
local_csv는 버전 자리에local을 쓴다. `pier_to_port`는 (source,port_id)와공식pier역할을 보존한다.
정부 시설코드나 TAGO/KOMSA 코드 동등성, 현재운항/시간표를 보장하지 않는다.

원문 DMS/flag15필드를 그대로 보존한다.0/공란·N/결측은 다르다. datum/CRS가 선언되지 않아
PortReference의latitude/longitude는None이며 관광지 대표좌표·다른 자료PRJ를 전이하지 않는다.

## 검토된 gid2 한 건

`reviewed_route_crosswalks(feature, receipt=archive_receipt, piers=rows)`에 검증한 원SHP feature와
receipt, 공식 선착장 rows를 넣으면 gid2에만 출발/도착 crosswalk 두개를 제공한다.
기존 `map_route(feature, ports=[pier_to_port(p) for p in rows if p.name], crosswalk=entries,
endpoint_kind='pier')`는 국동→외동과 주소·출처·수집시점·파생키를 포함한 시설 참조를 돌려준다.
원본 RouteEndpoints의출발/도착결측은 유지한다.

검토범위는 meta52/history2019-12-10/layer500048/piltg_rute_l/gid2,
제작일20220825/ENC KR64755B/객체600024와원WKB·raw/normalized속성전체지문이다.
해경 면허20210928 row55/20221007 row29/20231011 row14의 국동→외동 이름·주소와
공식 선착장20201020 row85국동/row84외동, 여수시 공식본문을 결합했다.
원선의vertex순서나 최근접거리 하나로 방향/이름을 정하지 않는다. 면허의거리원문0.5는
단위없는당시header그대로보존하며,독립형상길이495m와분리한다.
선착장flag는외동N/국동공란인시점·품질차이를고치지않는다.

작은 [검토 manifest](../src/vadahub/_reviewed_piltg.json)에 revision·공식근거URL/버전/해시/행·
품질차이를포함했다. 실제ArchiveSHA는매호출바인딩한다. ArchiveSHA가바뀌어도검토한레코드의
identity/WKB/raw/normalized속성전체가같을때만동일revision을쓸수있다.
다른행·ZIP전체동일성이나현재면허유효성을검토했다고주장하지않는다.
검토대상변경·행누락/중복·가짜출처는SchemaError이며새검토가필요하다.
다른33행은빈crosswalk로유지한다. 차트경계선분에전체면허양끝을복제하지않는다.

[설치본 실제 예제](../examples/reviewed_pier_mapping.py)는 신규경로인자 하나로
CSV/SHP다운로드→원자보관→GDAL→1매핑/33미확정과시설정보를실행한다.
원SHP의기본CRS미상은유지하며이매핑은좌표변환/최근접알고리즘을사용하지않는다.
상세근거는 [사양](external-resolution.md), 수집/파싱live는 [runbook](runbooks/live.md)을따른다.
