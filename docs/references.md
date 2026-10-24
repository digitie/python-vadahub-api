# 참조 저장소 분석

조사일: 2026-10-24 KST. 아래 SHA는 실제 읽은 로컬 checkout의 HEAD다.
참조 저장소의 미커밋 변경은 복사하지 않는다. 링크는 같은 SHA의 GitHub 원문이다.

| 저장소·기준 SHA | 읽은 부분 | 채택 | VadaHub 적용 차이 |
|---|---|---|---|
| [python-kric-api](https://github.com/digitie/python-kric-api/tree/55361313ad59f13e8699ebcbe130c532002b9b76) | pyproject, AGENTS, SKILL, docs, src/kric/storage.py, CI | src layout, typed package, provider 경계, docs/tasks/journal/resume, 검증 gate | `kric`→`vadahub`; 철도·서비스키·XLSX 의존 제외; Chromium·SHP 추가 |
| [python-opinet-api](https://github.com/digitie/python-opinet-api/tree/dcfb41a1862bb9718a778fdc0fc2e3e807ed7d47) | client.py, _http.py, _ratelimit.py, pyproject | native async, async with/aclose, 주입한 transport 소유권, 공유 token bucket | 확인한 checkout은 httpx 기반이며 Chromium 구현이 없음. 사용자 요구에 따라 VadaHub에서는 async Chromium transport 구현 |
| [python-mois-api](https://github.com/digitie/python-mois-api/tree/3cdee09eb753edbdaf91c28a955e2c6ddd72ec17) | files.py, docs/file-downloads.md | download/load/iter/load_file 역할 구분, 파일 I/O 분리, 로컬 원문 재로딩 | CSV→SHP+DBF+TXT; ZIP 제한·원자 보관·manifest 계약을 명시적으로 추가 |
| [kor-travel-transport](https://github.com/digitie/kor-travel-transport/tree/c6d7158cc5a3b4910ec74fee388480102d9b83a1) | models.py FerryPort/FerryTerminalReference, rail_maritime_collection.py, map-ferry-reference-export.md | `(source, port_id)` 식별, `_unique_port_call`의 지역+이름 유일성, 지침 좌표와 승선항구 분리 | runtime 의존 금지; 소비자가 typed 참조 목록을 주입; VadaHub ID와 TAGO/KOMSA ID 분리 |
| [python-krits-api](https://github.com/digitie/python-krits-api/tree/61b357fbd96413c90e40e4360ca4fef75dae96ec) | source-analysis.md, client.py, _browser.py, resume.md | 실제 ITS·node-link 담당 저장소가 이미 존재함을 확인 | ITS 범위 결정 전 이 저장소로 그대로 복제하지 않음. Chromium 참고는 출처를 명시 |

코드 재사용 시 원저작권·GPL 의무를 유지한다. 참조 구현의 동작이 자동으로 VadaHub 계약이
되지는 않는다. 테스트는 VadaHub의 공개 화면·실제 파일로 다시 검증한다.

## GDAL 추가 지시

사용자가 `kor-travel-geo`의 GDAL 활용을 명시했다. main 기준
[`5dec2981ef3842f1eb4e7942b0c58ff5c1cca6ba`](https://github.com/digitie/kor-travel-geo/tree/5dec2981ef3842f1eb4e7942b0c58ff5c1cca6ba)의
ADR-005와 `src/kortravelgeo/loaders/shp/polygons_loader.py`를 GitHub에서 확인했다.
로컬 `F:/dev/kor-travel-geo`에는 data만 있고, `kor-travel-geo-codex`는 Linux worktree여서
Windows Git으로 HEAD를 확인할 수 없다. 따라서 원격 SHA를 기준으로 명시했다.
`asyncio.to_thread`, Python GDAL binding, scoped `SHAPE_ENCODING=CP949`, 협조적 취소,
시스템/binding ABI 일치를 채택한다. geo의 PostGIS 적재·기존 EPSG:5179 강제는 가져오지 않는다.
VadaHub ZIP에 CRS가 없으므로 geo의 원천 CRS와 같다고 추정하지 않는다.

## T002 실제 재사용

KRIC의 src 패키지·py.typed·setuptools·pytest/mypy/coverage CI 구조를 VadaHub용으로 적용했다.
`_ratelimit.py`는 위 Opinet SHA의 공유 token bucket을 재사용했다.
Chromium 전용 `_browser.py`와 생명주기·redirect/소유권·취소 테스트는 위 `python-krits-api`
SHA의 파일을 출처로 사용해 VadaHub origin과 계약으로 수정했다. 이는 ITS 기능 구현을
가져온 것이 아니라 브라우저 기반 provider의 자원 관리 공통 코드다.
추가 source는 `src/krits/_browser.py`, `src/krits/exceptions.py`,
`tests/{conftest,test_client,test_ratelimit,test_live_browser}.py`다.
VadaHub의 title·컨테이너·공개 페이지 검증은 이 저장소에서 직접 구현·live 확인했다.
