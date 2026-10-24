# 설치·소비자 실행

Python3.11 이상, async Playwright Chromium을 사용한다. 키·로그인이 필요 없다.
카탈로그·웹 질의·원문 ZIP 보관은 GDAL 없이 사용할 수 있으며 SHP 파싱에는 GDAL Python
binding3.8 이상이 필요하다. 시스템 libgdal과 binding 버전을 맞춘다.

## Linux/WSL: 웹과 GDAL을 같은 환경에서 사용

저장소 루트에서 실행한다. 아래는 distro Python의 GDAL을 사용하는 방법이다.
오래된 배포판의 GDAL이3.8 미만이면 지원되는 시스템 환경을 먼저 준비한다.
임의 최신 `pip install gdal`로 시스템 ABI를 덮어쓰지 않는다.

```bash
sudo apt-get update
sudo apt-get install python3-gdal python3-venv
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install .
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python -c 'from osgeo import gdal; print(gdal.VersionInfo())'
.venv/bin/python examples/tourism.py experience_village artifacts/villages-new.zip --region 삼척
```

Playwright 설치는 브라우저와 OS 실행 의존성을 준비한다. 이미 준비된 Chromium은
예제의 `--chromium /absolute/path/to/chrome`으로 지정할 수 있다.
Windows와 WSL에서 같은 LocalArchiveStore에 동시 write하지 않는다.

시스템 Python 패키지가 많아 완전 격리가 필요하면 libgdal-dev·컴파일러·Python 개발
헤더가 준비된 환경에서 새 venv를 만들고 **gdal-config와 정확히 같은 버전**을 빌드할 수 있다.

```bash
/usr/bin/python3 -m venv /tmp/vadahub-isolated
/tmp/vadahub-isolated/bin/python -m pip install numpy "GDAL==$(gdal-config --version)"
/tmp/vadahub-isolated/bin/python -m pip install .
/tmp/vadahub-isolated/bin/python -m pip check
```

numpy는 이 native 환경의 GDAL 드라이버/배열 모듈 준비용이며 SDK core 의존성은 아니다.
시스템 GDAL3.12.2와 일치하는 binding을 빌드한 완전 격리 환경에서도 검증했다.

## Windows: core 설치와 웹 확인

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install .
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -I tools/verify_install.py
```

3.11~3.14 중 설치된 Python을 지정한다. 이 절차는 native GDAL을 설치하지 않는다.
SHP 호출 시 GDAL이 없으면 `SpatialDependencyError`다. 이 프로젝트의 실제 공간 검증은
로컬 WSL과 필수 Linux spatial CI에서 실행했다. Windows에서 받은 ZIP을 WSL로 읽을 때
동일 바이트의 SHA와 receipt를 대조한다. `.prj` 없는 좌표는 추정하지 않는다.

## wheel·sdist 및 설치본 확인

개발 환경에서 `python -m pip install -e '.[dev]'` 후 `python -m build`를 실행한다.
sdist에서 wheel을 빌드하며 docs/예제/설치 확인 도구도 sdist에 포함한다. wheel은
`vadahub`와 `py.typed`, metadata/license를 제공한다. 운영 설치는 빌드된 wheel로 검증할 수 있다.

```bash
python -m build
/usr/bin/python3 -m venv --system-site-packages /tmp/vadahub-consumer
/tmp/vadahub-consumer/bin/python -m pip install dist/*.whl
/tmp/vadahub-consumer/bin/python -I tools/verify_install.py --spatial
/tmp/vadahub-consumer/bin/python -m playwright install --with-deps chromium
/tmp/vadahub-consumer/bin/python -I examples/acceptance.py --output artifacts/consumer-new
```

새 venv 경로를 사용하고 기존 venv를 삭제하거나 덮어쓰지 않는다. `-I`는 PYTHONPATH와
저장소 src의 우연한 import를 막는다. verify_install은 현재 venv 내부의 vadahub 파일,
모든 공개 export·py.typed·설치 metadata를 검사하고 `--spatial`에서 실제 GDAL을 import한다.
CI는 Python3.11~3.14 각각 wheel을 별도 venv에 설치해 이 검사를 수행한다.

acceptance 예제는 실제 원천에 접속한다. 신규 output 아래 원문6개·보관소·receipt를 남기고
857행의 GDAL 계보/멱등 보관, 도선 출도착지 누락34건, 여객항로424건과 시설후보109건,
관광119+410건 및 invalid2, API124의 실제 필터를 검증한다. 이 예제의 고정 건수는 조사
snapshot이며 원천 변경 시 실패하게 설계했다. 수량이 바뀌면 사양·증빙을 재검토한다.
현재 여객터미널이 다운로드를 제공하게 된 경우도 조용히 성공으로 바꾸지 않고 조사하게 한다.

`examples/tourism.py`는 카테고리 하나를 받아 다운로드→보관→GDAL→지역 검색을 실행한다.
해수욕장은 `--preserve-invalid`가 없으면 원문 품질 오류를 반환한다. 기존 destination은
덮어쓰지 않는다. 현재 영업·허가·개장일 정보로 과거 조사자료를 사용하지 않는다.

## 검증 단계

```bash
python -m compileall -q src/vadahub tests examples tools
python -m mypy src/vadahub
python tools/check_docs.py
python -m pytest -m 'not live' --cov=vadahub --cov-fail-under=90
```

90% coverage 검사는 GDAL이 있는 환경에서 실행한다. Windows의 native skip을 성공으로
계산하지 않는다. live 전체를 환경변수 없이 한 번에 실행하는 대신
[live 실행 절차](runbooks/live.md)에 따라 웹 수집과 동일 원문 파싱을 순서대로 실행한다.
[최종 검증 증빙](validation/t008.md)과 [외부 제약](tasks.md)을 함께 읽는다.
선택적인 S3 adapter·서버·스케줄러·운영 DB는 이번 구현에 포함하지 않았다.
