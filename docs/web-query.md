# OpenAPI 안내에 연결된 공개 웹 질의

실제 공개 UI와 같은 Chromium 세션에서 schema/샘플을 읽고 DataTables 페이지를 조회한다.
키가 필요한 인증 OpenAPI의 파라미터/응답과 동일하다고 주장하지 않는다.
공개된 기능에만 연결하며 key·로그인·인증 fallback이 없다.

```python
async with VadaHubClient() as client:
    services = await client.list_datasets(catalog='api_original')
    service = next(item for item in services if item.api_id == '124')
    resource = (await client.list_resources(service))[0]
    page = await client.query_table(resource, page_size=10)
    print(page.total, page.filtered_total, page.columns, page.rows)
```

66개 안내에 연결자료65개를 실제 조사했다. 하나는 기초자료가 없고, 일부 지도/가공 안내는
metadata의 grid Y와 달리 실제 공개 schema/행이 없다. 해당 경우 DownloadUnavailableError로
반환한다. 401/403/429/잘못된 HTML·schema를 정상 빈 결과로 바꾸지 않는다.

API140/142는 UI의 goOpnDetail처럼 실제 backing meta5247/5248을 사용한다.
LibraryResource.dataset은 원 catalog meta/API ID를 보존하고 backing_dataset_id는 실제 자료 meta다.
마스킹·비공개·MEMBER와 원본 table 변경은 거부한다. schema를 매번 원천과 재대조한다.

`query_table`은 start0..1000000, page_size1..200의 단일 페이지다. 필터는 원천 JSON column
이름에 대한 문자열(각128자/최대200개), 정렬은 원천에 있는 column만 허용한다.
UI와 같은 column 검색/정렬 요청을 전송하며 SQL table이나 필드명을 호출자가 임의 지정하지 않는다.
JSON은 최대2MiB이며 통신/lock대기/질의를 포함한 operation timeout과 기본1RPS를 적용한다.
원천의 setRecordsTotal과 recordsFiltered를 각각 total/filtered_total로 보존하며 단일 페이지의
행수가 선언된 범위를 채우지 못하면 오류다. 다중 호출은 일관된 DB snapshot이라고 보장하지 않는다.
대규모 전체 순회를 기본 실행하지 않는다. 범위를 좁혀 페이지를 요청하는 것은 소비자의 책임이다.

WebTablePage.columns는 JSON camelCase 키, source_columns는 원 schema의 snake_case 키다.
두 이름을 대조하여 labels를 정확히 연결하고 미기재 설명은 None으로 둔다. 일자·코드는
웹 원문 문자열 그대로 보존한다. 숫자 좌표 속성이 있다고 CRS나 유효 시점으로 추정하지 않는다.

`VadaHubFileClient.list_api_layers(service)`는 backing 공간 layer만 반환하며 기존
download/load/load_file/GDAL API와 연결한다. 미제공 버튼·SHP·미확인 CRS는 기존 계약과 같다.
자료실의 get_table_preview는 별도 partial UI snapshot이며 이 페이지 API와 혼동하지 않는다.

원천 API139(파랑3분)는 실제 grid 호출에서 150초 통신 실패를 확인했다. 이 서비스의 실제
조회 성공은 T007A2E 외부제약/미완료로 남긴다. SDK는 NetworkError를 반환하며 자동 재시도하지 않는다.
live는 해당 실패와 성공 서비스를 별도 집계한다. 목록 발견/실패 전파를 조회 성공이라고 표시하지 않는다.
권한 제한, 연결자료0, 실제 schema/행0 역시 정상 데이터 조회 성공과 별도다.

실제 OPEN API144의 ZIP은 polygon119개 중4개가 invalid다. 기본 공간 로더는 이를 거부한다.
`invalid_geometry='preserve'`를 명시하면 원문 WKB와 geometry_valid=False를 보존하고
WGS84 변환을 생략한다. 자동 보정하거나 정상 geometry로 표시하지 않는다. 읽기·인코딩 경고는
그대로 오류이며 IsValid의 invalid 경고만 이 옵션에서 수용한다. null/empty geometry의
geometry_valid는 None이다. 원본 attributes/SHA/CRS 근거도 그대로 제공한다.
