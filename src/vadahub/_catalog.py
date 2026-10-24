"""검증한 top-level 웹 응답만 카탈로그 타입으로 바꾼다."""
from datetime import date
import re
from typing import Any

from ._browser import BASE_URL
from .exceptions import SchemaError
from .models import CatalogKind, Dataset, DatasetLayer, LibraryResource

CATALOG_PATHS: dict[CatalogKind, tuple[str, str, str]] = {
    'space': ('/renew/spaceData/index.do','/renew/spaceData/list.do','/renew/spaceData/detail.do'),
    'documents': ('/renew/docData/index.do','/renew/docData/list.do','/renew/docData/detail.do'),
    'statistics': ('/renew/statsData/index.do','/renew/statsData/list.do','/renew/statsData/detail.do'),
    'api_original': ('/bigdata/openApiRenew/index.do','/bigdata/openApiRenew/list.do','/bigdata/openApiRenew/detail.do'),
    'api_analysis': ('/bigdata/openApiRenew/indexAnal.do','/bigdata/openApiRenew/listAnal.do','/bigdata/openApiRenew/detail.do'),
    'api_map': ('/bigdata/openApiRenew/indexMap.do','/bigdata/openApiRenew/listMap.do','/bigdata/openApiRenew/detail.do'),
}


def backing_meta(dataset: Dataset) -> str:
    meta = identifier(dataset.dataset_id)
    if dataset.catalog.startswith('api_'):
        api_id = identifier(dataset.api_id)
        return {'140':'5247','142':'5248'}.get(api_id,meta)
    return meta


def text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError('필수 문자열이 없거나 잘못됐습니다')
    return value.strip()


def identifier(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise SchemaError('잘못된 자료 ID입니다')
    result = str(value)
    if not re.fullmatch(r'[0-9]+', result):
        raise SchemaError('자료 ID는 ASCII 숫자 문자열이어야 합니다')
    return result


def history(value: Any) -> str:
    result = text(value)
    try:
        if date.fromisoformat(result).isoformat() != result:
            raise ValueError()
    except ValueError:
        raise SchemaError('잘못된 메타 이력일자입니다') from None
    return result


def count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchemaError('잘못된 원천 수량입니다')
    return value


def rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get('resultList'), list):
        raise SchemaError('resultList 계약이 바뀌었습니다')
    result = payload['resultList']
    if not all(isinstance(item, dict) for item in result):
        raise SchemaError('자료 행이 객체가 아닙니다')
    return result


def parse_dataset(row: dict[str, Any], catalog: CatalogKind = 'space') -> Dataset:
    meta, hist = identifier(row.get('metaSn')), history(row.get('histDe'))
    description = row.get('factorCn12')
    if description is not None and not isinstance(description, str):
        raise SchemaError('잘못된 자료 설명 타입입니다')
    api_id = identifier(row.get('odtaId')) if catalog.startswith('api_') else None
    request = row.get('odtaReqstUrl')
    if request is not None and not isinstance(request,str):
        raise SchemaError('잘못된 OpenAPI 안내 URL')
    formats = row.get('extsnType')
    if formats is not None and not isinstance(formats,str):
        raise SchemaError('잘못된 OpenAPI 포맷')
    # 공개 UI goOpnDetail의 140/142 안내는 별도 backing meta로 이동한다.
    detail_meta = {'140':'5247','142':'5248'}.get(api_id or '',meta) if catalog.startswith('api_') else meta
    suffix = f'&odtaId={api_id}' if api_id else ''
    return Dataset(meta, hist, text(row.get('metaNm')), description or '',
                   f'{BASE_URL}{CATALOG_PATHS[catalog][2]}?metaSn={detail_meta}&histDe={hist}{suffix}',
                   catalog, api_id, request if request and request != '-' else None, formats)


def flag(value: Any) -> bool:
    if value not in ('Y', 'N'):
        raise SchemaError('Y/N 상태 계약이 바뀌었습니다')
    return value == 'Y'


def optional_flag(value: Any) -> bool | None:
    if value is None or (isinstance(value,str) and not value.strip()):
        return None
    return flag(value)


def parse_layer(row: dict[str, Any], meta: str, hist: str) -> DatasetLayer:
    if identifier(row.get('metaSn')) != meta or history(row.get('histDe')) != hist:
        raise SchemaError('다른 meta의 기초자료가 섞였습니다')
    table = text(row.get('relateDtaNm'))
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', table):
        raise SchemaError('안전하지 않은 layer 이름입니다')
    return DatasetLayer(meta, hist, identifier(row.get('bsisDtaSn')), table,
                        text(row.get('bsisDtaNm')), text(row.get('serviceAuthCd')),
                        text(row.get('opnScopeSe')), flag(row.get('gridOpenYn')),
                        flag(row.get('dwldPosblYn')), optional_flag(row.get('maskingYn')))


def parse_resource(row: dict[str, Any], dataset: Dataset) -> LibraryResource:
    if identifier(row.get('metaSn')) != dataset.dataset_id or history(row.get('histDe')) != dataset.history_date:
        raise SchemaError('다른 meta의 자료실 resource입니다')
    kind = row.get('atrbSpceSe')
    if not isinstance(kind,str):
        raise SchemaError('자료 속성 구분이 없습니다')
    source_format = row.get('orginlTableNm')
    if source_format is not None and not isinstance(source_format,str):
        raise SchemaError('자료 포맷 형식 오류')
    auth = row.get('serviceAuthCd')
    if auth is not None and not isinstance(auth,str):
        raise SchemaError('자료 공개 상태 형식 오류')
    raw = tuple((name,row.get(name)) for name in ('serviceAuthCd','gridOpenYn','dwldPosblYn','maskingYn'))
    if not all(value is None or isinstance(value,str) for _,value in raw):
        raise SchemaError('자료 공개 원문 형식 오류')
    return LibraryResource(dataset,identifier(row.get('bsisDtaSn')),text(row.get('bsisDtaNm')),
                           text(row.get('relateDtaNm')),source_format,kind,
                           auth.strip() or None if auth is not None else None,text(row.get('opnScopeSe')),
                           optional_flag(row.get('gridOpenYn')),optional_flag(row.get('dwldPosblYn')),optional_flag(row.get('maskingYn')),
                           raw_availability=raw)
