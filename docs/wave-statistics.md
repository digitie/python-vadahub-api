# 3분 격자 파랑 공개 웹 통계

`VadaHubClient.get_wave3min_statistics`는 인공지능 해양정보 화면의 날짜·격자 한정 통계를
조회한다. 3분은 공간 격자 해상도이며 시간별 관측 원행이나 실시간 정보를 뜻하지 않는다.
API139 안내/연결자료의 공개상태를 매번 확인하고 실제 화면과 같은 POST를 사용한다.
키·로그인·인증 API fallback이 없다.

```python
from datetime import date
from vadahub import VadaHubClient

async def read_wave():
    async with VadaHubClient(timeout=60) as client:
        result = await client.get_wave3min_statistics(
            'GR3_F4J12_H', start_date=date(2018, 6, 10),
            end_date=date(2018, 6, 11), measure='height')
        for row in result.rows:
            print(row.analysis_date, row.value, row.raw_attributes)
        print(result.resource.dataset.api_id, result.source_url, result.collected_at)
```

measure는height(원문wvhgh) 또는period(원문pd)다. 입력은date 날짜 양끝 포함 최대7개,
격자1개다. datetime/날짜 문자열·범위 역전·임의 SQL/table/URL은 받지 않는다.
카탈로그 발견부터 실제 통계 응답까지 전체 메서드 본체에 설정 timeout을 적용하며,
중단 시 기존 브라우저의 유한 cleanup 유예가 추가될 수 있다. limiter는 기존과 공유한다.

WaveStatistics는 원resource/질의기간/측정종류·원천URL/UTC수집시점을 보존한다.
각 WaveStatistic은 grid_code/analysis_date/value와 immutable 원문속성을 제공한다.
숫자0·null을 구분하고 다른 격자·범위 밖/중복 날짜·잘못된/무한수·schema 변경을 오류로
반환한다. 정상이지만 자료가 없는 기간은 빈 tuple이며 누락 날짜를0으로 채우지 않는다.
누락 날짜의 이유나 요청기간 전체의 완전성은 추정하지 않는다. 단위/집계식도 원문 UI 근거
없이 API 원행과 같다고 주장하지 않는다. 자료의 조사/분석 시점과 수집일은 별개다.

이 메서드는 일반 `query_table`과 별개다. API139의 일반 DataTables는 gid필터에서도
45초 실패를 다시 확인했다. 49건 원행 조회 성공 집계에 통계 성공을 더하지 않는다.
자동으로 두 경로 사이를 전환하거나 성공 형식을 바꾸지 않는다.
실행 가능한 CLI는 [wave_statistics.py](../examples/wave_statistics.py)다.
