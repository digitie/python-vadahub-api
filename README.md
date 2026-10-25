# python-vadahub-api

VadaHub(해양수산부 공동활용체계)의 공개 웹페이지와 공간자료 ZIP/SHP를
키 없이 수집·해석하는 **비동기 Python provider 라이브러리**다.
공간자료 카탈로그·공개 ZIP 다운로드, GDAL 파싱과 async load/iter/local API,
선착장 상세·근거에 따른 매핑을 제공한다.
원문 SHA 버전 보관과 manifest 복구, 공개 안내·자료실과 웹 테이블 질의를 제공한다.
추가 [관광9종](docs/tourism.md)의 카탈로그·SHP·검색과 [실행 예제](examples/tourism.py)를 제공한다.
[시각별 파랑 원값](docs/wave-hourly.md)과 [파랑 날짜·격자 웹 통계](docs/wave-statistics.md)는 일반 테이블 원행과 구분해 제공한다.
[공식 터미널 CSV 보완](docs/terminal-supplement.md)은 별도 출처로 명시적으로 선택할 수 있다.
T008까지 구현 PR 머지와 격리 설치본 검증을 완료했다. [완료 기록](docs/tasks-done.md)과
[외부 미해결 항목](docs/tasks.md)을 구분해 확인할 수 있다.

주요 대상은 [공간 데이터](https://vadahub.go.kr/renew/spaceData/index.do)의
관광지정보, 여객터미널, 도선항로, 여객항로다. 웹 접근은 Chromium을 사용한다.
별도의 API 키를 요구하거나 인증 OpenAPI로 자동 전환하지 않는다.

## 현재 확인한 한계

- 관광지정보는 단일 파일이 아닌 4개 기초자료다. 화면의 `전체보기`로 펼쳐야 한다.
- 여객터미널(`psnr_trml_p`)은 현재 부분 공개·다운로드 미제공이다.
  관광지정보 아래의 여객선(`pssh_p`) 자료와 별도 원본으로 취급한다.
- 실제 도선항로 SHP 34건에는 출도착지 필드와 이름이 없다.
  여객항로에는 `strpnt_nm`, `prtcl_nm`, `dstntn_nm`이 있다.
- 조사한 SHP ZIP은 `c1..cN` DBF와 실제 필드명을 설명하는 CP949 TXT를 포함하고,
  `.prj`는 없다. 미확인 CRS를 EPSG:5179 등으로 추정하지 않는다.
- OpenAPI 안내66개 중 실제 웹 조회 성공은49개 resource다. API139의 통신 실패와
  권한 제한·연결자료/공개 grid 부재를 별도로 기록한다. 인증 API 동등 응답을 보장하지 않는다.
- 과거 관광자료의 기준/제작일·조사년도와 이름 결측, 해수욕장의 invalid 도형2건을 보존한다.

이 차이를 숨기지 않고 출처·원문·미매핑 상태를 제공하는 것이 구현 계약이다.
사용자가 ITS는 오기임을 확인했으며 이번 대상은 VadaHub뿐이다.

## 문서

- [실제 제공자료 조사](docs/source-analysis.md)
- [설치·wheel·실행 예제](docs/installation.md), [단계별 live 절차](docs/runbooks/live.md)
- [기능·데이터·오류·보관 상세 사양](docs/specification.md)
- [구조](docs/architecture/architecture.md)
- [참조 저장소와 재사용 결정](docs/references.md)
- [실행 순서](docs/implementation-plan.md), [작업 목록](docs/tasks.md)
- [독립 적대적 리뷰 2명 및 live E2E 머지 규칙](docs/runbooks/hostile-review.md)
- [검증 기록](docs/validation/t001.md), [재개 지점](docs/resume.md)

원문 다운로드·파싱·파일 보관은 이 저장소, 주기 수집·운영 DB·외부 서비스 제공은
소비자의 책임이다. `kor-travel-transport`의 DB나 코드를 런타임 import하지 않는다.

## 구현된 async 기반 사용

Python 3.11 이상에서 `python -m pip install .` 후
`python -m playwright install chromium`으로 Chromium을 준비한다.
SHP parser에는 시스템 GDAL 3.8 이상과 같은 버전의 Python binding을 먼저 준비해야 한다.
현재 core 설치와 페이지 확인에는 GDAL·API 키가 필요 없다.

```python
import asyncio
from vadahub import VadaHubClient

async def main() -> None:
    async with VadaHubClient(timeout=60) as client:
        snapshot = await client.get_page_snapshot()
        print(snapshot.title, snapshot.source_url, snapshot.collected_at)

asyncio.run(main())
```

이 결과는 공개 공간자료 페이지 접근 확인이다. 자료 수집은 다음 카탈로그/파일 API를 사용한다.
`executable_path`로 설치된 Chromium을 지정하거나 `browser_context`로 Chromium context를
주입할 수 있다. 주입한 context는 호출자가 닫고 SDK가 만든 page는 SDK가 닫는다.
동일 loop의 여러 SDK가 `AsyncTokenBucket`을 공유할 수 있다. 기본 1 RPS·burst 1은
operation 제한이며 브라우저 자산 요청량 제한이 아니다. 자동 재시도는 하지 않는다.
401/403·로그인·보안 확인은 `AccessDeniedError`, 429는 `RateLimitError`, 통신/timeout은
`NetworkError`, 제목/컨테이너 변경은 `SchemaError`로 노출한다.

`timeout`은 operation 본체의 제한이다. 취소 후 생성/종료 command별로 추가 정리 유예
`cleanup_timeout`(기본 5초)를 둔다. 이 유예도 넘으면 client를 종료 상태로 전환해 다음
operation을 차단하고, 늦게 생성/종료되는 소유 자원은 background로 추적한다.
외부 context는 이때도 닫지 않는다. 응답이 끝내 오지 않으면 pending 정리가 해당 context/
driver 종료까지 남을 수 있다. `aclose()`의 반복 호출은 이 pending 응답을 무한 대기하지 않는다.

## 카탈로그·공개 ZIP 다운로드

```python
from pathlib import Path
from vadahub import VadaHubFileClient

async def download_ferry() -> None:
    async with VadaHubFileClient(timeout=120) as client:
        datasets = await client.list_datasets()
        dataset = next(item for item in datasets if item.title == '도선항로')
        layers = await client.list_layers(dataset)
        receipt = await client.download(layers[0], Path('dosun.zip'))
        print(receipt.sha256, receipt.byte_size)
```

`list_datasets(page_size=50,max_pages=20)`는 total·중복·중간 빈 페이지와 페이지 상한을
검증한다. `list_layers(dataset)`는 meta의 이력키를 보존한다. `get_availability(layer)`로
현재 상태를 다시 확인한다. 다운로드도 매번 원천 상태를 재조회한다.
동일 주입 BrowserContext를 사용하는 여러 SDK의 operation은 같은 잠금으로 직렬화한다.
기존 출력 파일은 덮어쓰지 않으며 신규 파일을 임시 저장·ZIP 검증 뒤 원자 공개한다.
`ArchiveLimits`로 원문/해제크기·멤버수·압축비를 제한한다. 브라우저의 원문 수신이 끝난 뒤
적용되는 상한이므로 수신 중 브라우저 임시 디스크의 사용량을 제한한다고 보장하지 않는다.
`DownloadUnavailableError`는 미제공 자료이며 정상 빈 결과가 아니다.

```bash
python -m pip install -e '.[dev]'
python -m pytest -m 'not live' --cov=vadahub --cov-fail-under=90
python -m mypy src/vadahub
```

live 실행에 설치된 Chromium 경로를 지정하려면 `VADAHUB_CHROMIUM_EXECUTABLE` 환경변수를
사용한다. SDK 자체는 이 변수를 자동 탐색하지 않고 테스트가 명시적으로 전달한다.
실제 원문을 받는 단계와 GDAL 파싱 단계는 [live 실행 절차](docs/runbooks/live.md)를 따른다.

## GDAL 공간자료 로딩

```python
from contextlib import aclosing
from vadahub import VadaHubFileClient

async def read_archive(layer) -> None:
    async with VadaHubFileClient() as client:
        async with aclosing(client.iter_file('dosun.zip', layer=layer)) as rows:
            async for row in rows:
                print(row.record_id, row.attributes, row.geometry_type)
```

`load_file`은 전체 목록, `iter_file`은 bounded batch를 반환한다. `load(layer)`와
`iter(layer)`는 다운로드와 임시 ZIP의 수명도 관리한다. 반복을 일찍 끝낼 때는
`aclosing`으로 iterator를 닫는다. GDAL 객체는 하나의 worker에서 생성·사용·해제한다.
취소 시 worker 종료를 기다리므로 native 읽기가 멈춰 있으면 취소 완료도 지연될 수 있다.
원문 WKB와 raw DBF 속성, TXT로 복원한 속성, 원문 SHA256을 함께 제공한다.
날짜 필드의 유효한 YYYYMMDD는 `date`, 빈 문자열은 `None`, 코드/전화는 문자열로 보존한다.
`.prj`가 없으면 CRS와 WGS84 WKB는 `None`이다. `source_crs`를 명시하면 근거를
기록하고 변환하며, 원문 `.prj`와 충돌하면 `UnknownCrsError`다.
Windows에서 GDAL이 없으면 공간 호출만 `SpatialDependencyError`로 실패한다.
[설치·ABI·필수 공간 CI](docs/gdal.md)를 따른다.

## 조사 재현

`list_datasets(catalog=...)`는 기본 `space` 외에 `documents`, `statistics`, `api_original`,
`api_analysis`, `api_map`을 지원한다. OpenAPI 안내의 API ID·포맷·신청 안내 URL을 보존한다.
문서/통계는 `list_resources(dataset)`로 파일·테이블을 발견한다. 공개 PDF URL은
`get_document_preview(resource)`, 통계 UI snapshot은 `get_table_preview(resource)`다.
이는 API 키를 쓰는 서비스의 전체 응답을 보장하지 않는다. 실제 확인한 연안기본조사 ZIP은
`download_library(resource,destination)` 후 같은 `LocalArchiveStore.put(receipt)`로 보관한다.
[전체 안내 목록과 지원 범위](docs/public-catalogs.md)를 확인한다.

OpenAPI 안내도 `list_resources(dataset)`로 공개 backing 자료를 발견하고
`query_table(resource,start=0,page_size=50,filters={'column':'value'},order_by='column')`로
실제 공개 웹 테이블을 조회한다. 결과의 원천 total·필터 total·정렬된 schema·수집시점을
보존한다. `list_api_layers(dataset)`의 backing 공간 layer는 기존 download/load로 연결한다.
[웹 질의 상세 계약](docs/web-query.md)은 인증 API와의 차이와 자료 미제공을 설명한다.

선착장 상세는 `ports_from_features(pssh_rows)`로 제공한다. `port_from_transport(dto,
collected_at=...,source_url=...)`는 transport ferry-ports-v1 개별 항구 DTO를 변환한다.
`map_route(feature,ports=...)`는 전체 출도착지·구간명·기항 원문·각 endpoint 상태와
후보/확정 선착장 상세를 반환한다. 자세한 계약과 예는 [매핑 문서](docs/mapping.md)에 있다.

Python 3.11 이상에서 `python -m pip install playwright`와
`python -m playwright install chromium`을 실행한다. 이미 설치된 Chromium은
`--executable-path`로 지정할 수 있다.

```bash
python tools/probe_source.py --output-dir artifacts/t001 --download
```

로그인 없이 공개 버튼으로만 다운로드한다. 내려받지 못한 자료를 성공으로 기록하지 않는다.
실행마다 비어 있는 새 output 디렉터리를 지정한다. 기존 성공 receipt와 재생성 ZIP을 섞지 않는다.
실행 결과 원문·쿠키·대용량 ZIP은 저장소에 커밋하지 않는다.

라이선스는 기존 저장소의 GPL-3.0-or-later를 따른다. 원천자료의 이용조건은 별도로
보존하며 라이브러리 코드의 라이선스로 원천자료의 재배포 권한을 대체하지 않는다.

공간 파서는 `kor-travel-geo`와 같이 **GDAL Python binding**을 사용한다.
`ogr2ogr` subprocess는 사용하지 않는다. 시스템 GDAL과 Python binding의 ABI를 맞추는
방법과 async worker 계약은 [GDAL 설계](docs/gdal.md)를 따른다.
