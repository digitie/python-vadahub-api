# 로컬 원문 버전 보관

```python
from vadahub import LocalArchiveStore

store = LocalArchiveStore('data/vadahub')
stored = await store.put(receipt)
versions = await store.versions(receipt.layer)
recovered = await store.recover()
```

`objects/<meta>/<history>/<layer>/<table>/<SHA256>/archive.zip`과 receipt.json을 함께
immutable 디렉터리로 공개하고 manifest.json을 원자 교체한다. 호출자가 반환 경로를 직접
수정하면 다음 읽기 검증에서 오류다. SDK는 기존 성공 원문을 덮어쓰거나 삭제하지 않는다.
같은 scope+ZIP SHA면 기존 버전/수집시점을 재사용한다. 다른 ZIP SHA는 새 버전으로 남기며
`content_fingerprint`(정렬한 멤버 이름+payload SHA)로 생성시각만 다른 ZIP을 구분한다.
versions는 삽입 순서이며 자료의 의미상 최신성을 추정하지 않는다.

사전 크기 상한과 복사 중 바이트 상한, 원문/멤버 해시·크기·CRC를 재검증한다. 파일 I/O와
cross-process filelock은 worker에서 실행한다. 기본 lock_timeout은 5초이며 충돌 시
filelock.Timeout이다. 같은 root에 서로 다른 OS(Windows/WSL) writer를 섞거나 분산/네트워크
FS 잠금으로 사용하지 않는다. 저장소 디렉터리는 호출자가 신뢰·관리하는 로컬 경로여야 한다.

stage 취소는 공개하지 않는다. commit worker 시작 뒤 취소는 원자 commit이 끝날 수 있으며
종료까지 기다린다. 이 경우 `versions`/`recover`로 완료 여부를 확인한다. 이전 성공 버전은
남는다. 원문 공개 뒤 manifest 교체 실패는 이전 manifest와 새 object를 보존한다.
`recover`는 고아 receipt 경로·해시·크기를 재검증하고 정상 원문만 manifest에 원자 추가한다.
손상 metadata/원문은 오류이며 자동 삭제/덮어쓰기로 숨기지 않는다. schema_version은 1,
manifest 상한 8MiB, 고아 검사 상한 10000개다. 정전·디스크 하드웨어 내구성은 FS/OS 정책에 따른다.

S3는 이 구현의 필수 범위가 아니다. 별도 버킷/자격증명이 명시되고 실제 roundtrip을
검증할 수 있을 때 adapter task로 추가한다. 환경의 비밀값을 자동 탐색하지 않는다.
