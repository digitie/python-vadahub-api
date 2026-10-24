# GDAL 활용 상세 결정

사용자 지시: `kor-travel-geo`의 GDAL 활용. 기준 구현은
[ADR-005](https://github.com/digitie/kor-travel-geo/blob/5dec2981ef3842f1eb4e7942b0c58ff5c1cca6ba/docs/adr/005-gdal-python-binding-loader.md)와
[polygons_loader.py](https://github.com/digitie/kor-travel-geo/blob/5dec2981ef3842f1eb4e7942b0c58ff5c1cca6ba/src/kortravelgeo/loaders/shp/polygons_loader.py)다.

## 채택할 구현

- `osgeo.gdal/ogr/osr` Python binding을 사용하며 `ogr2ogr` subprocess를 쓰지 않는다.
- 동기 binding 작업은 `asyncio.to_thread` 또는 전용 bounded worker에서 실행한다.
  각 dataset/layer/feature/geometry는 같은 worker에서 열고 읽고 닫는다.
- reader는 `gdal.OpenEx(..., gdal.OF_VECTOR, open_options=["ENCODING=CP949"])`로 연다.
  `gdal.config_options({"SHAPE_ENCODING":"CP949"}, thread_local=True)`는 worker 내부
  컨텍스트로 한정한다. 전역 `SetConfigOption`, import 시 `UseExceptions`를 호출하지 않는다.
- 변환이 필요하면 `gdal.VectorTranslate` 옵션·progress callback과 협조적 취소를 사용한다.
  단순 읽기에 PostGIS 변환을 끼워 넣지 않는다. dataset보다 먼저 자식 객체를 해제하고
  native 객체는 async 경계 밖으로 반환하지 않는다.
- 원시 geometry는 WKB/검증된 좌표 구조로 복사한다. GeoJSON이라고 이름 붙여 미확인 CRS의
  투영 좌표를 WGS84로 가장하지 않는다.
- 호출자 취소 시 worker에 thread-safe cancel flag를 전달하고 worker 종료를 기다린 뒤
  ZIP 임시경로를 지운다. async task 취소가 native 작업을 즉시 멈춘다고 가정하지 않는다.
  GDAL 변환 callback과 feature/batch 경계마다 취소를 검사한다.
- `osr.SpatialReference`와 `CoordinateTransformation`에 traditional GIS axis order를
  명시한다. `.prj`/호출자 CRS 근거가 없으면 변환하지 않는다. geo loader의 고정 5179를
  VadaHub에 가져오지 않는다.
- ZIP을 GDAL에 넘기기 전에 stdlib ZIP 검증을 수행한다. 검증한 로컬 `/vsizip/`만 읽고
  `/vsicurl/`, 원격 GDAL VFS, 임의 driver의 네트워크 접근을 사용하지 않는다.

GDAL은 `.prj`, `.cpg`와 DBF codepage를 해석하지만 익명 필드를 동봉 TXT로 복원하는
VadaHub 계약은 별도로 구현해야 한다. multipart의 개별 feature geometry 유형도 검사한다.
근거: [GDAL Shapefile driver](https://gdal.org/en/stable/drivers/vector/shapefile.html).
dataset 자식 객체 수명은 [Python binding 주의사항](https://gdal.org/en/stable/api/python/python_gotchas.html),
thread-local 설정은 [General API](https://gdal.org/en/stable/api/python/general.html)를 따른다.

## 설치와 CI

GDAL은 native ABI 의존성이므로 core 카탈로그/브라우저 기능과 `spatial` extra를 분리한다.
GDAL이 없으면 공간 메서드에서 구체적인 설치 오류를 내고 카탈로그 기능은 동작한다.
Linux/WSL에서 시스템 `libgdal`과 **같은 버전**의 Python binding을 설치한다.
시스템 Python의 distro `python3-gdal`을 쓰거나 `gdal-config --version`과 동일한 버전으로
환경을 만든다. 임의 최신 `pip install gdal`을 권하지 않는다. 설치한 실제 버전과 ABI를
검증 기록에 남긴다.

GDAL integration CI는 binding이 있는 Linux 환경에서 필수 실행한다.
GDAL 미설치로 skip한 Windows unit 실행을 공간 파서 검증 성공으로 계산하지 않는다.
fixture 단위 테스트와 함께 실제 공개 ZIP→GDAL 전 행→TXT 필드복원→모델 반환 E2E를 수행한다.

## 실제 준비 상태

T004 구현은 GDAL 3.8 이상을 요구한다. Linux의 시스템 Python binding을 쓰는 예:

```bash
sudo apt-get install python3-gdal python3-venv
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -c 'from osgeo import gdal; print(gdal.VersionInfo())'
.venv/bin/python -m pytest -m 'not live' --cov=vadahub --cov-fail-under=90
```

필수 `spatial` CI가 실제 GDAL로 전체 unit과 90% coverage gate를 실행한다.
Python 3.11~3.14 core matrix는 binding 없이 core·빌드를 검증한다.
로컬 live는 Windows Chromium으로 새 ZIP을 받은 뒤 같은 원문의 SHA를 WSL GDAL에서
대조하는 두 환경으로 실행한다. `VADAHUB_LIVE_ARCHIVES`로 원문의 디렉터리를 전달한다.
원문은 재생성 ZIP이므로 ZIP 해시와 멤버 해시를 구분해 보관한다.

현재 Windows Python에는 `osgeo`가 없다. WSL `Ubuntu-26.04`의 Python에는
GDAL `3120200`(3.12.2) binding이 있어 실제 받은 원문 ZIP을 대상으로 별도 읽기 검증한다.
이번 단계에서는 geo 저장소의 DB·운영 컨테이너·데이터를 변경하지 않는다.
