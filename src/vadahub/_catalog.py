"""검증한 top-level 웹 응답만 카탈로그 타입으로 바꾼다."""
from datetime import date
import re
from typing import Any

from ._browser import BASE_URL
from .exceptions import SchemaError
from .models import Dataset, DatasetLayer


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


def parse_dataset(row: dict[str, Any]) -> Dataset:
    meta, hist = identifier(row.get('metaSn')), history(row.get('histDe'))
    description = row.get('factorCn12')
    if description is not None and not isinstance(description, str):
        raise SchemaError('잘못된 자료 설명 타입입니다')
    return Dataset(meta, hist, text(row.get('metaNm')), description or '',
                   f'{BASE_URL}/renew/spaceData/detail.do?metaSn={meta}&histDe={hist}')


def flag(value: Any) -> bool:
    if value not in ('Y', 'N'):
        raise SchemaError('Y/N 상태 계약이 바뀌었습니다')
    return value == 'Y'


def parse_layer(row: dict[str, Any], meta: str, hist: str) -> DatasetLayer:
    if identifier(row.get('metaSn')) != meta or history(row.get('histDe')) != hist:
        raise SchemaError('다른 meta의 기초자료가 섞였습니다')
    table = text(row.get('relateDtaNm'))
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', table):
        raise SchemaError('안전하지 않은 layer 이름입니다')
    return DatasetLayer(meta, hist, identifier(row.get('bsisDtaSn')), table,
                        text(row.get('bsisDtaNm')), text(row.get('serviceAuthCd')),
                        text(row.get('opnScopeSe')), flag(row.get('gridOpenYn')),
                        flag(row.get('dwldPosblYn')))
