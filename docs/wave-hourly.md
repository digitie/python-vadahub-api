# 시각별 파랑 재분석 원값

`VadaHubClient.get_wave3min_hourly`는 API139의 공개 상태를 매번 확인하고, 인공지능 해양정보
공개 WFS 두 뷰에서 같은 격자·날짜·시각의 파고/파향/평균주기를 조회한다.
3분은 공간 해상도다. 날짜별 집계나 실시간 센서 관측이 아닌 시각별 AI 재분석 값이다.

```python
from datetime import date
from vadahub import VadaHubClient

async def read_hourly():
    async with VadaHubClient(timeout=90) as client:
        result = await client.get_wave3min_hourly(
            'GR3_F4J12_H', analysis_date=date(2018, 6, 10), hour=18)
        for row in result.rows:
            print(row.wave_height, row.wave_direction, row.mean_wave_period)
            print(row.height_attributes, row.period_attributes)
        print(result.source_url, result.type_names, result.collected_at)
```

입력은 ASCII GR3 격자1개/date1개(datetime 제외)/0..21의3시간 간격 정수 시각1개다.
공개 API139/resource520360와 OPEN/ALL/비마스킹·grid 상태, 화면·WFS capabilities/필드를
확인한 뒤 고정 두 타입에 maxFeatures2와 날짜/시각·격자 equality를 요청한다.
다른 URL/type/CQL/SQL/XML을 caller가 주입할 수 없다. 키·로그인·자동 재시도/fallback은 없다.

응답의 count/동일 identity/유한 nullable 값과 두 뷰의 원 geometry/파향 일치를 검증한다.
두 뷰 모두0건이면 빈 tuple이고 한쪽만 있거나 중복이면 SchemaError다.
접근 거부·429·전송 오류/HTML·XML 예외는 명시적 오류다. 원문2MiB 상한과 전체 작업 timeout,
공유 limiter/context lock/소유권·취소/유한 cleanup은 기존 클라이언트와 같다.
XML DTD/entity를 거부하며 schemaLocation·내부망 주소를 따라가지 않는다.

`WaveHourlyRecord`의 두 immutable 속성, 원 FID 및 feature JSON(파싱 후 재직렬화)은
각각 원천 뷰를 구분한다. geometry는 원 JSON으로만 보존하고 좌표를 파생하지 않는다.
WFS FID는 원 opn gid가 아니다. 원13필드 중 gid/lo/la/wvlen/생성자·생성시점은 제공하지 않는다.
일반 query_table의 DataTables13필드 성공 수량에 이 기능을 더하지 않는다.

검토 사양은 [외부 원천](external-resolution.md), 설치본 소비 예제는
[wave_hourly.py](../examples/wave_hourly.py)다. live는 VADAHUB_HOURLY_ARTIFACTS의 신규경로에
`python -m pytest tests/test_live_wave_hourly.py --run-live -q -s`로 실행한다.
