# AGENTS.md

`python-vadahub-api`는 VadaHub 공개 웹·파일 provider SDK다. 정식 remote는
`https://github.com/digitie/python-vadahub-api.git`, 기준 브랜치는 `origin/main`이다.

## 작업 순서

`CLAUDE.md` → `AGENTS.md` → `SKILL.md` → `docs/architecture/architecture.md` →
`docs/specification.md` → `docs/tasks.md` → `docs/resume.md`를 읽는다.
사용자 지시가 이 문서보다 우선한다. 문서·주석·docstring은 한국어로 작성하고
URL·필드명·원문 코드는 보존한다.

1. 상세 사양과 task를 먼저 문서 PR로 만든다. 문서 PR 머지 전 구현을 시작하지 않는다.
2. 모든 작업은 `origin/main`에서 분기한 `codex/` 브랜치와 Draft PR로 진행한다.
   `main`에 직접 push하지 않는다.
3. **각 PR은 서로 독립적인 적대적 리뷰어 2명과 변경 범위에 맞는 실제 live E2E 검증을
   모두 통과한 뒤 머지한다. 머지 확인 후에만 다음 task 구현에 착수한다.**
4. 리뷰어는 별도 agent/context 두 개로 실행한다. 작성자의 자체 점검 두 번으로
   대체하지 않는다. A는 데이터·공간·매핑 계약, B는 async·파일·보안·운영 실패를 검토한다.
5. P0/P1/P2 지적은 수정·재검증·재리뷰한다. CI 실패, 미해결 지적, live 실패/미실행은
   머지 차단 사유다. 외부 제한은 증빙과 함께 task를 미완료로 남긴다.
6. 리뷰와 live 검증은 최종 구현 SHA에 연결한다. 증빙 문서만 추가한 경우에도
   코드가 변하지 않았음을 확인하고 최종 SHA의 CI를 확인한다.
7. [리뷰 runbook](docs/runbooks/hostile-review.md)의 evidence 형식을 따른다.

## 필수 구현 원칙

- API 키가 없다. Playwright의 async Chromium으로 공개 웹 기능을 사용한다.
  API 키 발급 안내나 인증 API fallback을 추가하지 않는다.
- 호출 한도를 피하기 위한 키 회전·우회·CAPTCHA 해결을 구현하지 않는다.
  401/403/429와 로그인/보안 확인은 명시적 오류이며 재시도 폭주를 금지한다.
- `python-kric-api`의 src layout·provider 경계·문서 체계를 카피해 맞춘다.
  철도 전용 코드·fixture·인증키·버전 이력을 통째로 복사하지 않는다.
- async 생명주기·공유 제한은 `python-opinet-api`, 파일 download/load/iter 계약은
  `python-mois-api`를 참조한다. 적용 차이는 `docs/references.md`에 기록한다.
- SHP 읽기·좌표변환은 `kor-travel-geo`의 GDAL Python binding 패턴을 사용한다.
  `ogr2ogr` subprocess·pyshp 기반 production parser·전역 GDAL 설정 변경은 금지한다.
  [GDAL 설계](docs/gdal.md)의 ABI·thread·취소·dataset 생명주기를 따른다.
- 원본 meta와 layer ID, 코드 문자열, CP949 TXT 필드 매핑, 미확인 CRS를 보존한다.
  도선항로와 여객항로, 여객터미널과 관광지정보의 여객선을 서로 대체하지 않는다.
- 매핑은 transport의 `(source, port_id)`를 보존한다. 동명·다중 후보·원천 출도착지 누락은
  미해결 상태로 반환한다. 지도 선의 첫/끝 vertex를 근거 없이 출발/도착으로 지정하지 않는다.
- ZIP은 자동 extractall하지 않는다. 경로·중복·멤버수·해제크기·압축비·CRC를 검증한다.
- 원문·해시·manifest는 원자적으로 공개하고 실패·취소로 이전 성공 버전을 훼손하지 않는다.
- 스케줄러·FastAPI 서버·운영 DB 모델을 provider에 넣지 않는다.

## 검증 및 기록

T001 문서 단계는 `git diff --check`, 문서 링크 확인, 실제 Chromium 조사 재현으로 검증한다.
T002 이후에는 다음과 PR별 live E2E를 통과해야 한다.

```bash
python -m compileall src/vadahub tests
python -m mypy src/vadahub
python -m pytest -m "not live" --cov=vadahub --cov-fail-under=90
```

live는 [단계별 절차](docs/runbooks/live.md)의 환경변수·신규 원문 경로를 준비해 해당
테스트를 실행한다. clean wheel 소비자 E2E는 [설치 문서](docs/installation.md)를 따른다.

live 테스트의 skip은 성공이 아니다. unit 테스트는 네트워크를 사용하지 않는다.
종료·취소·할당량·깨진 ZIP·동명 항구·CRS 미상 같은 실패 경계를 우선 검증한다.
완료 시 `docs/journal.md`, `docs/resume.md`, `docs/tasks.md`, `docs/tasks-done.md`,
해당 `docs/validation/` 증빙을 갱신한다. 미래 일을 완료로 표시하지 않는다.
