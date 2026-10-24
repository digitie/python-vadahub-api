# 공개 안내·자료실의 지원 범위

2026-10-24 실제 Chromium 조사. 원 OpenAPI40, 분석가공25, 지도1, 문서451, 통계73.
목록은 조회 중 total 변경·중복·페이지 상한을 검증한다. OpenAPI 식별에는 meta/history에
API ID도 포함한다. API140/142의 상세화면 backing meta 변경은 공개 goOpnDetail과 같다.
API 신청 URL은 안내 정보이며 SDK가 접속하거나 키를 발급/사용하지 않는다.

| 기능 | 상태 | Python 계약과 근거 |
|---|---|---|
| 3종 OpenAPI 전체 안내 탐색 | 지원 | list_datasets(catalog=api_original/api_analysis/api_map), 66개 서비스 ID·제목·설명·포맷·안내 URL |
| 키가 필요한 서비스의 파라미터·응답 완전 동등성 | 미지원 | 공개 backing 웹 질의는 별도 query_table 계약이며 인증 응답과 동일하지 않음 |
| 공개 backing 웹 데이터 | 지원/원천별 제약 | list_resources(api Dataset) → query_table, 전체66개 안내의 실제 가용성은 검증 기록 참조 |
| 문서/통계 자료실 탐색 | 지원 | documents/statistics와 list_resources; 파일명·포맷·공개/조회/다운로드를 분리 |
| 공개 PDF 보기 | 부분 | get_document_preview; 원문 URL만, 미제공 다운로드를 우회하지 않음 |
| 공개 통계 화면 데이터 | 부분 | get_table_preview; UI sampleApiList GET의 snapshot, 권위 total 부재로 partial=True |
| 연안기본조사 공개 ZIP | 지원 | meta700101의 OPEN/ALL/비마스킹/다운로드Y 및 실제 zipDown 버튼 재확인 |
| 다른 파일 프로토콜/마스킹/비공개 자료 | 미지원 | 명시 오류. 버튼/메타 모순을 임의로 허용하지 않음 |
| 공간 SHP·관광자료 | 지원/확장 중 | 기존 공간 API와 T007B; 개별 원천의 가용성·CRS·품질 제한 적용 |

`get_table_preview`는 표시 column/label과 원 JSON의 추가 필드도 보존한다. 코드 문자열을
숫자로 변환하지 않는다. snapshot의 행수가 전체 OpenAPI total이라는 보장이 없다.
미리보기 가능하지만 다운로드N인 PDF를 `download_library`로 저장하지 않는다.
`list_resources`는 문서/통계/OpenAPI 안내의 실제 연결자료를 재조회한다. 임의 SQL table로 변환하지 않는다.

자료실 ZIP은 `LibraryArchiveReceipt`를 반환한다. `LocalArchiveStore.put`/`versions(resource)`로
같은 검증·멱등·고아복구를 사용한다. 경로는 objects/library/catalog/meta/history/resource/SHA다.
ZIP의 안전한 디렉터리는 허용하되 경로/중복/암호화/symlink/CRC/자원 제한은 유지한다.
자동 해제하지 않는다. 원문의 비UTF8 ZIP 멤버명은 raw CP437 해석명과 해시를 보존하며
CP949로 이름을 추정 복원하거나 그 이름으로 로컬 경로를 생성하지 않는다.

```python
async with VadaHubFileClient() as client:
    documents = await client.list_datasets(catalog='documents')
    survey = next(d for d in documents if d.dataset_id == '700101')
    resources = await client.list_resources(survey)
    public = next(r for r in resources if r.resource_id == '720006')
    receipt = await client.download_library(public, 'coastal.zip')
    stored = await LocalArchiveStore('data').put(receipt)
```

[서비스별 66개 목록](openapi-inventory.md)은 안내 조회 지원과 데이터 질의 미지원/부분을
명확히 구분한다. 인증 OpenAPI 응답 schema와 동일하다고 주장하지 않는다.
