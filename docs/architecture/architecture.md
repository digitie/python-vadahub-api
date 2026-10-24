# 구조

이 저장소는 Python provider SDK다. KRIC 저장소의 디렉터리 구조를 기반으로 한다.
아래 `src`와 `tests`는 T002 이후 순서대로 구현할 목표 구조다.

```text
python-vadahub-api/
├── AGENTS.md / CLAUDE.md / SKILL.md
├── pyproject.toml
├── src/vadahub/
│   ├── __init__.py / py.typed
│   ├── client.py          # 공개 async facade·카탈로그
│   ├── _browser.py        # Chromium 소유권·직렬화·timeout·정리
│   ├── _ratelimit.py      # 공유 async 호출 예산
│   ├── models.py / exceptions.py
│   ├── files.py           # UI 다운로드·load/iter
│   ├── parse.py           # ZIP 검증·DBF/TXT/geometry
│   ├── mapping.py         # 출도착지→선착장 매핑
│   └── storage.py         # 원문·checksum·manifest, 선택적 S3
├── tests/fixtures/        # 합성/비밀값 제거 fixture
├── tools/probe_source.py  # 실제 공개 화면 조사
└── docs/
    ├── architecture/ / runbooks/ / validation/
    ├── source-analysis.md / specification.md / references.md
    └── implementation-plan.md / tasks.md / tasks-done.md / journal.md / resume.md
```

## 데이터 흐름

```text
VadaHub 공개 화면 → async Chromium → 카탈로그·기초 layer 목록
                                     ↓ 공개 UI 다운로드
                             임시 ZIP → 무결성 검사 → 원문/manifest
                                                    ↓
                                    SHP+DBF+TXT → SpatialFeature
                                                    ↓
소비자가 주입한 선착장 참조/crosswalk ────────────────→ 매핑 결과
                                                    ↓
                                     kor-travel-transport 등 소비자
```

## 생명주기

생성자는 네트워크·프로세스를 만들지 않는다. 첫 operation에서 Chromium을 지연 생성하고
한 세션의 navigation/download는 lock으로 직렬화한다. 특히 서버의 SHP 생성→다운로드가
세션 상태를 사용하므로 두 layer의 생성/다운로드를 섞으면 안 된다.
주입한 BrowserContext는 닫지 않고 생성한 page만 닫는다. 자체 생성 driver/browser/context는
역순 정리한다. 종료는 멱등이며 실패·취소 후 listener·page·부분 파일을 정리한다.
다른 event loop에서의 재사용은 오류다. 종료와 진행 중 operation의 경쟁도 테스트한다.

대용량 디스크 I/O와 ZIP/DBF/CRS 계산은 thread로 넘기되 취소 후에도 thread의 쓰기가
계속되는 문제를 고려해 완료 대기·파일 소유권을 명시한다. bounded batch로 async iterator를
제공하고 `load()`는 명시적 전량 적재 편의 API로 둔다.

## 의존성과 범위

Python >=3.11, setuptools, Playwright, GDAL Python binding을 채택한다.
GDAL은 선택적 `spatial` 기능이며 시스템 GDAL과 binding 버전을 맞춘다.
SHP 읽기는 `gdal.OpenEx`, 좌표변환은 `osr.CoordinateTransformation`, 필요 시
포맷 변환은 `gdal.VectorTranslate`를 사용한다. 상세는 [GDAL 설계](../gdal.md)다.
core에는 웹서버·Pandas·GeoPandas·DB·수집 스케줄러를 넣지 않는다.
typed dataclass와 Protocol 경계로 browser/storage/참조 항구를 교체할 수 있게 한다.
원문 파일의 보관 정책과 주기 갱신은 소비자가 결정한다.
S3 호환 저장소는 선택 기능이며 명시적으로 전달한 설정만 사용한다.
