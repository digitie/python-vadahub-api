"""실제 공개 ZIP을 검증한 관광자료의 원천별 필드 계약. 서로 다른 시점은 합치지 않는다."""
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
import re
import unicodedata
from urllib.parse import urlsplit

from .exceptions import SchemaError
from .models import DatasetLayer, SpatialFeature


@dataclass(frozen=True, slots=True)
class TourismSource:
    """고정 식별자와 원천 필드. history는 registry에 고정하지 않고 현재 catalog에서 얻는다."""
    category: str
    title: str
    dataset_id: str
    layer_id: str
    table_name: str
    name_field: str
    address_field: str | None = None
    phone_field: str | None = None
    website_field: str | None = None
    region_fields: tuple[str, ...] = ()
    region_code_field: str | None = None
    detail_fields: tuple[str, ...] = ()
    year_field: str | None = None
    date_field: str | None = None
    date_meaning: str | None = None


TOURISM_SOURCES = (
    TourismSource('beach', '해수욕장', '520621', '520621', 'beach', 'beach_name'),
    TourismSource('experience_village', '어촌체험마을(기준일 자료)', '520624', '520624',
        'fsvlg_exprnc_vlg', 'vlg_nm', address_field='loc_adrs', website_field='homepage',
        region_fields=('sido_nm', 'sgg_nm'), detail_fields=('prgr_nm1', 'prgr_nm'),
        date_field='data_std', date_meaning='자료기준일'),
    TourismSource('observatory', '전망대', '113', '500113', 'obpv_p', 'obpv_nm',
        address_field='fcl_raddr', region_code_field='area_sclas_cd', detail_fields=('fct_nm',), year_field='invs_yr'),
    TourismSource('freshwater_fishing', '민물낚시터', '49', '500045', 'fwtr_fshlc_p', 'fwtr_fshlc_nm',
        address_field='fcl_lnm_addr', detail_fields=('main_knfs_list',), date_field='mfgg_ymd', date_meaning='제작일'),
    TourismSource('sea_fishing', '바다낚시터', '50', '500046', 'sea_fshlc_p', 'sea_fshlc_nm',
        address_field='fcl_lnm_addr', detail_fields=('main_knfs_list',), date_field='mfgg_ymd', date_meaning='제작일'),
    TourismSource('coastal_walk', '해안산책로(지점)', '115', '500115', 'cwlk_p', 'cwlk_nm',
        region_code_field='area_sclas_cd', detail_fields=('trl_dstc_cn',), year_field='invs_yr'),
    TourismSource('marina', '마리나정보', '106', '500106', 'mrn_info_a', 'mrna_nm',
        address_field='all_addr', phone_field='mrna_tno', website_field='hmpg_url_addr',
        region_fields=('adm_zn_nm',), detail_fields=('tour_info', 'mrna_utlz_info')),
    TourismSource('rock_fishing', '갯바위낚시포인트', '108', '500108', 'rsp_p', 'pnt_nm',
        region_fields=('adm_zn_nm',), region_code_field='sgg_cd', detail_fields=('fshg_mth_trget_cn',)),
    TourismSource('experience_village_legacy', '어촌체험마을(조사년도 자료)', '3078', '501308',
        'fvex_vllg_p', 'fvex_vllg_nm', phone_field='fvex_vllg_tno', region_code_field='area_sclas_cd',
        detail_fields=('etc_ref_cn',), year_field='invs_yr'),
)


def tourism_source(category: str) -> TourismSource:
    """정확한 category만 받는다. 별칭·동명 자료로 자동 대체하지 않는다."""
    for source in TOURISM_SOURCES:
        if source.category == category:
            return source
    raise ValueError(f'지원하지 않는 관광 category: {category!r}')


@dataclass(frozen=True, slots=True)
class TourismLayer:
    source: TourismSource
    layer: DatasetLayer


@dataclass(frozen=True, slots=True)
class TourismPlace:
    """관광 검색용 요약. 모든 원문 속성·geometry·품질·수집 계보는 feature에 남긴다."""
    source: TourismSource
    feature: SpatialFeature
    name: str | None
    address: str | None
    phone: str | None
    website: str | None
    region: str | None
    region_code: str | None
    details: tuple[tuple[str, str], ...]
    survey_year: int | None
    source_date: date | None

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        """시점/원문 버전이 다른 같은 gid를 구분한다."""
        layer = self.feature.layer
        return layer.dataset_id, layer.history_date, layer.layer_id, self.feature.record_id, self.feature.source_sha256


def _text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaError('관광 문자열 필드의 형식이 바뀌었습니다')
    return value.strip() or None


def _website(value: str | None) -> str | None:
    if value is None:
        return None
    # 표시용 URL만 반환하며 방문/다운로드하지 않는다. 원문은 feature에 보존한다.
    if any(ord(c) <= 32 or ord(c) == 127 for c in value) or '\\' in value:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            return None
        _ = parts.port
    except ValueError:
        return None
    return value


def tourism_from_feature(feature: SpatialFeature, *, category: str) -> TourismPlace:
    """검증한 layer의 정식 속성만 투영한다. 결측 이름·좌표·조사년도를 만들어내지 않는다."""
    source = tourism_source(category)
    layer = feature.layer
    if (layer.dataset_id, layer.layer_id, layer.table_name) != (source.dataset_id, source.layer_id, source.table_name):
        raise SchemaError('관광 category와 원본 layer identity가 다릅니다')
    attrs = feature.attributes

    def field(key: str | None) -> str | None:
        if key is None:
            return None
        if key not in attrs:
            raise SchemaError(f'관광 원천 필드가 없습니다: {key}')
        return _text(attrs[key])

    year = field(source.year_field)
    if year is not None and not re.fullmatch(r'[0-9]{4}', year):
        raise SchemaError('관광 조사년도 형식이 바뀌었습니다')
    raw_date = attrs.get(source.date_field) if source.date_field else None
    if source.date_field and source.date_field not in attrs:
        raise SchemaError(f'관광 원천 필드가 없습니다: {source.date_field}')
    parsed_date = None
    if raw_date is not None:
        if type(raw_date) is date:
            parsed_date = raw_date
        else:
            text = _text(raw_date)
            if text is not None:
                try:
                    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', text):
                        raise ValueError
                    parsed_date = date.fromisoformat(text)
                except ValueError as exc:
                    raise SchemaError('관광 기준/제작일 형식이 바뀌었습니다') from exc
    regions = tuple(value for key in source.region_fields if (value := field(key)) is not None)
    details = tuple((key, value) for key in source.detail_fields if (value := field(key)) is not None)
    return TourismPlace(source, feature, field(source.name_field), field(source.address_field),
        field(source.phone_field), _website(field(source.website_field)), ' '.join(regions) or None,
        field(source.region_code_field), details, int(year) if year else None, parsed_date)


def search_tourism(places: Iterable[TourismPlace], *, name_contains: str | None = None,
                   region_contains: str | None = None) -> Iterator[TourismPlace]:
    """호출자가 제공한 행을 지연 검색한다. 지역명은 region 또는 주소, 행정코드는 별도 원문이다."""
    def normalized(value: str | None) -> str:
        return unicodedata.normalize('NFC', value or '').strip().casefold()
    name, region = normalized(name_contains), normalized(region_contains)
    for place in places:
        if name and name not in normalized(place.name):
            continue
        if region and region not in normalized(place.region) and region not in normalized(place.address):
            continue
        yield place
