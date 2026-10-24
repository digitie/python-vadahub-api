# python-vadahub-api

VadaHub(해양수산부 공동활용체계)의 공개 웹페이지와 공간자료 ZIP/SHP를
키 없이 수집·해석하는 **비동기 Python provider 라이브러리**다.
상세 사양 문서 PR #1을 머지했고, 현재 T002 async 기반을 구현했다.
공간자료 목록·다운로드·GDAL 파싱·매핑은 이후 task이며 아직 제공하지 않는다.

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

이 차이를 숨기지 않고 출처·원문·미매핑 상태를 제공하는 것이 구현 계약이다.
사용자가 ITS는 오기임을 확인했으며 이번 대상은 VadaHub뿐이다.

## 문서

- [실제 제공자료 조사](docs/source-analysis.md)
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
SHP parser 구현 단계에서는 시스템 GDAL과 같은 버전의 binding을 먼저 준비해야 한다.
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

이 결과는 공개 공간자료 페이지 접근 확인이며 4종 자료를 수집한 결과가 아니다.
`executable_path`로 설치된 Chromium을 지정하거나 `browser_context`로 Chromium context를
주입할 수 있다. 주입한 context는 호출자가 닫고 SDK가 만든 page는 SDK가 닫는다.
동일 loop의 여러 SDK가 `AsyncTokenBucket`을 공유할 수 있다. 기본 1 RPS·burst 1은
operation 제한이며 브라우저 자산 요청량 제한이 아니다. 자동 재시도는 하지 않는다.
401/403·로그인·보안 확인은 `AccessDeniedError`, 429는 `RateLimitError`, 통신/timeout은
`NetworkError`, 제목/컨테이너 변경은 `SchemaError`로 노출한다.

```bash
python -m pip install -e '.[dev]'
python -m pytest -m 'not live' --cov=vadahub --cov-fail-under=90
python -m mypy src/vadahub
python -m pytest -m live --run-live
```

live 실행에 설치된 Chromium 경로를 지정하려면 `VADAHUB_CHROMIUM_EXECUTABLE` 환경변수를
사용한다. SDK 자체는 이 변수를 자동 탐색하지 않고 테스트가 명시적으로 전달한다.

## 조사 재현

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
