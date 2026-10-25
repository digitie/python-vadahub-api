# live 실행 절차

API 키 없이 Chromium 공개 UI로 실제 접속한다. 각 실행은 신규 artifact 경로를 사용한다.
원문이 바뀌었거나 접근 제한·schema·통신 실패가 나면 gate를 통과시킨 것으로 기록하지 않는다.
자동 재시도·키 fallback이 없다. 아래는 저장소 루트에서 실행하는 회귀 절차다.
clean wheel 최종 소비자 검증은 [설치 문서](../installation.md)의 acceptance 예제를 사용한다.

## 1. 웹 수집

아래는 GDAL이 없는 Windows에서도 실행 가능하다. `RUN`이라는 신규 실행명을 정하고
`artifacts/RUN-*`가 존재하지 않는지 확인한다. 기존 receipt와 새 ZIP을 섞지 않는다.
브라우저 경로를 지정하지 않으면 Playwright가 설치한 Chromium을 사용한다.

```powershell
$env:PYTHONIOENCODING='utf-8'
# 필요할 때만 명시: $env:VADAHUB_CHROMIUM_EXECUTABLE='C:\absolute\path\chrome.exe'
$env:VADAHUB_LIVE_ARTIFACTS='artifacts/RUN-core'
$env:VADAHUB_PUBLIC_ARTIFACTS='artifacts/RUN-public'
$env:VADAHUB_QUERY_ARTIFACTS='artifacts/RUN-query'
$env:VADAHUB_TOURISM_ARTIFACTS='artifacts/RUN-tourism'
python -m pytest tests/test_live_browser.py tests/test_live_files.py tests/test_live_public_catalogs.py tests/test_live_query.py tests/test_live_tourism_download.py --run-live -q -s
```

API139의 기존 실제 통신 실패는 query live에서 성공과 별도로 `source_network_failed`로
기록한다. 다른 서비스에서 새 네트워크 실패가 생기면 테스트도 실패한다. 해당 예외 허용은
전체66서비스 데이터 성공을 뜻하지 않는다. API139 해결은 T007A2E 미완료 항목이다.

## 2. 같은 ZIP의 GDAL·매핑·보관 검증

앞 단계의 수집이 성공한 뒤 GDAL 환경에서 **같은 바이트**를 읽는다. 로컬 WSL은 Windows
F: 경로를 `/mnt/f/`로 접근할 수 있다. WSL venv에 프로젝트와 dev 의존성을 설치하고 실행한다.

```bash
export VADAHUB_LIVE_ARCHIVES=artifacts/RUN-core
export VADAHUB_QUERY_ARTIFACTS=artifacts/RUN-query
export VADAHUB_TOURISM_ARTIFACTS=artifacts/RUN-tourism
python -m pytest tests/test_live_spatial.py tests/test_live_mapping.py tests/test_live_storage.py tests/test_live_api_spatial.py tests/test_live_tourism_spatial.py --run-live -q -s
```

live skip은 성공이 아니다. transport 연결의 기존 live fixture는 계약 검증용이며 실제
항구 export의 정확한 도선 매핑을 증명하지 않는다. 도선의 원문 출도착지 부재와 터미널
다운로드 미제공은 T005E에 남긴다. 공통 모델·프로토콜이 변하면 관련 모든 live 단계를
재실행하며, 변경 범위가 제한된 PR은 runbook의 SHA 규칙에 따라 해당 live를 실행한다.

Linux에서 웹과 GDAL을 함께 준비했다면 두 단계를 같은 환경에서 실행할 수 있다.
PowerShell의 변수 설정을 `export`로 바꾸고 Python/Chromium 경로를 해당 환경에 맞춘다.
원문·프로필·쿠키는 커밋하지 않고 sanitized receipt와 실행 SHA·성공/실패/skip을 기록한다.

## 공식 선착장과 검토 매핑

신규 VADAHUB_PIER_ARTIFACTS 경로에 `tests/test_live_pier_download.py --run-live`로
실제 공식CSV를 받는다. 같은 실행의 신규 VADAHUB_LIVE_ARTIFACTS에서test_live_files를실행한다.
GDAL환경의VADAHUB_LIVE_ARCHIVES를그동일경로로설정하고
`tests/test_live_reviewed_mapping.py --run-live`를실행한다. 결과는선착장340/도선34/검토1/미확정33과
원문출도착지결측·DMS미선언/구조좌표None·보관/멱등/복구를함께검증한다.
[설치 예제](../../examples/reviewed_pier_mapping.py)의새경로실행으로격리wheel소비도확인한다.
