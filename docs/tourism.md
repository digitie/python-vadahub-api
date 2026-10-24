# 추가 관광자료

2026-10-24 실제 공개 UI ZIP과 GDAL 원문 조사에 따라 다음 9종을 제공한다.
`TOURISM_SOURCES`는 고정 meta/layer/table과 해석 필드의 registry이며 이력 날짜는
`list_tourism_layers(category=None)`가 현재 카탈로그에서 얻는다. 이름이 같은 자료를
자동 교체하거나 합치지 않는다. ID 변경·필드 누락은 SchemaError다.

| category | 자료 / meta / layer / table | 실제 행 | 원천 시점·특성 |
|---|---|---:|---|
| beach | 해수욕장 / 520621 / 520621 / beach | 410 | polygon, invalid2; created_date는 공개 시스템 생성일이며 개장일이 아님 |
| experience_village | 어촌체험마을 / 520624 / 520624 / fsvlg_exprnc_vlg | 119 | data_std 기준일2023-04-24, 체험 프로그램·주소·홈페이지 |
| observatory | 전망대 / 113 / 500113 / obpv_p | 112 | invs_yr 조사2014, 시설·주소 |
| freshwater_fishing | 민물낚시터 / 49 / 500045 / fwtr_fshlc_p | 554 | mfgg_ymd 제작2016-12-04, 이름 결측 행 보존 |
| sea_fishing | 바다낚시터 / 50 / 500046 / sea_fshlc_p | 219 | mfgg_ymd 제작2016-12-04, 어종·주소 |
| coastal_walk | 해안산책로 / 115 / 500115 / cwlk_p | 142 | 조사2014, POINT 지점과 거리 설명; 전체 선형 코스 아님 |
| marina | 마리나정보 / 106 / 500106 / mrn_info_a | 39 | MULTIPOINT, 주소·대표전화·홈페이지·이용 설명, 조사시점 미상 |
| rock_fishing | 갯바위낚시포인트 / 108 / 500108 / rsp_p | 1076 | 지역명·낚시방법·대상어종, 조사시점 미상 |
| experience_village_legacy | 어촌체험마을 / 3078 / 501308 / fvex_vllg_p | 226 | 조사2014, 대표전화·체험 설명; 119건 자료와 별도 원본 |

총2897행은 조사 snapshot이다. 미래 건수를 보장하지 않는다. 모두 원 ZIP에 PRJ/CPG가
없어 source_crs/WGS84는 미상으로 둔다. 속성 위경도나 DMS 값으로 geometry CRS를
추정하지 않는다. 해수욕장의 invalid 도형은 기본 거부하며 명시적으로
`invalid_geometry='preserve'`를 선택하면 원 WKB와 `geometry_valid=False`를 보존한다.
자동 수정·invalid 도형 좌표변환을 하지 않는다.

`TourismPlace`는 nullable 이름·주소·대표전화·홈페이지·지역명/행정코드·설명·조사년도와
기준/제작일을 제공한다. 날짜의 의미는 `place.source.date_meaning`으로 구분한다.
원문 `SpatialFeature`에는 모든 속성·geometry·해시·수집시점·원 meta/layer/이력이 남는다.
`key`는 meta/history/layer/record/hash로 버전을 구분한다. 이름 결측을 주소나 gid로
채우지 않는다. 이름/지역 부분 검색은 NFC·양끝 공백·casefold만 정규화하며 서버 검색을
가장하지 않는다. `search_tourism`은 전달받은 행을 지연 검색하고 지역은 원문 지역명 또는
주소에서 찾는다. 행정코드는 region_code 별도 필드다.

낚시터의 rel_dept_tno는 담당 행정부서 전화이므로 장소 전화로 승격하지 않는다.
새 체험마을의 ceonm/ceophno는 원문에만 두고 대표 연락처로 제공하지 않는다.
홈페이지는 http(s)·host·무인증 URL만 표시하며 SDK가 외부 사이트를 방문하지 않는다.
현재 운영·개장·낚시 허가·안전을 이 과거 자료로 보장하지 않는다.

metadata 공개범위(MEMBER 등)와 실제 비로그인 SHP 버튼의 제공 상태를 각각 보존한다.
접근 거부/로그인/429를 우회하지 않으며 다운로드는 매번 실제 상태와 공개 버튼을 확인한다.
API backing 공간 layer의 추가 공개/마스킹 정책은 기존대로 적용한다.

## 사용

```python
from vadahub import VadaHubFileClient, search_tourism

async def find_villages():
    async with VadaHubFileClient(timeout=120) as client:
        places = await client.load_tourism('experience_village')
        for place in search_tourism(places, region_contains='삼척'):
            print(place.name, place.address, place.source_date, place.feature.source_sha256)
```

원문을 보관하려면 `list_tourism_layers` → `download` → `LocalArchiveStore.put` →
`load_file(receipt=...)` → `tourism_from_feature(feature,category=...)`를 사용한다.
`iter_tourism`은 bounded GDAL iterator를 사용하고 조기 종료는 `contextlib.aclosing`으로
닫는다. `load_tourism`은 max_features 상한 내 전량 메모리 적재다.
[실행 예제](../examples/tourism.py)는 신규 출력 경로를 요구한다.

## 조사했으나 지원 확정하지 않은 자료

- 숙박업체 meta3077/layer501307: PARTIAL/MEMBER/downloadN.
- 해안누리길 meta5093: wgis_road 다운로드120초 timeout, tb_road 실제 SHP 버튼 없음.
- 마리나 추천항로5059·시설5058·예정구역5060: 다운로드 미제공.
- meta520620: layer와 meta/history 연결 불일치. 검증을 완화해 다른 원본으로 대체하지 않음.

이 자료들은 가용 9종에 포함하지 않는다. 실제 원천이 개선되면 같은 리뷰/live/CI 절차로
registry를 확장한다. 자료의 현재 가용성은 상시 보장되는 서비스 SLA가 아니다.
