"""공식 자료를 독립 검토한 한 도선 레코드에만 적용되는 외부 crosswalk."""
from collections.abc import Iterable, Mapping
from datetime import date, datetime
import hashlib
from importlib.resources import files
from itertools import islice
import json
import math
import re
from typing import Any

from ._pier_file import SOURCE, SOURCE_URL, CONTENT_DATE
from .exceptions import SchemaError
from .mapping import EndpointCrosswalk
from .models import ArchiveReceipt, OfficialPier, SpatialFeature

_REVIEW = json.loads(files('vadahub').joinpath('_reviewed_piltg.json').read_text(encoding='utf-8'))


def _fingerprint(attributes: Mapping[str, Any]) -> str:
    """문자열 코드·date·실수 표현을 구분한 검토 속성 지문."""
    for value in attributes.values():
        if (value is not None and type(value) not in (str, int, float, date)
                or type(value) is float and not math.isfinite(value)):
            raise SchemaError('검토 레코드 속성 타입/유한수 오류')
    raw = json.dumps(dict(attributes), ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                     allow_nan=False, default=lambda value: {'date': value.isoformat()})
    return hashlib.sha256(raw.encode()).hexdigest()


def reviewed_route_crosswalks(feature: SpatialFeature, *, receipt: ArchiveReceipt,
                               piers: Iterable[OfficialPier]) -> tuple[EndpointCrosswalk, ...]:
    """원문 결측은 유지하며 gid2 국동→외동의 동일 레코드 검토만 현재 SHA에 연결한다.

    파일 로더에서 검증한 feature/receipt와 공식 선착장 레코드를 전달한다. 다른33행에는
    빈 tuple을 반환한다. 검토 대상의 변경·중복/누락·출처 위조는 오류이며 재검토가 필요하다.
    전체 ZIP 동일성·현재 면허/운항·TAGO 코드 동등성을 주장하지 않는다.
    """
    layer = feature.layer
    identity = '/'.join((layer.dataset_id, layer.history_date, layer.layer_id, layer.table_name, feature.record_id))
    if layer.table_name != 'piltg_rute_l' or feature.record_id != '2':
        return ()
    if identity != _REVIEW['scope']:
        raise SchemaError('검토 대상 도선 원천 버전 변경: 새 검토가 필요합니다')
    if (not isinstance(receipt, ArchiveReceipt) or receipt.schema_version != '1'
            or receipt.layer != layer or receipt.source_url != layer.source_url
            or receipt.sha256 != feature.source_sha256 or not re.fullmatch('[a-f0-9]{64}', receipt.sha256)
            or not isinstance(receipt.collected_at, datetime) or receipt.collected_at.tzinfo is None
            or receipt.collected_at.utcoffset() is None or feature.source_collected_at != receipt.collected_at
            or layer.service_auth != 'OPEN' or layer.open_scope != 'ALL' or layer.masked is not False
            or feature.record_id_field != _REVIEW['record_id_field']
            or feature.geometry_type != _REVIEW['geometry_type'] or feature.geometry_wkb is None
            or hashlib.sha256(feature.geometry_wkb).hexdigest() != _REVIEW['wkb_sha256']
            or _fingerprint(feature.raw_attributes) != _REVIEW['raw_attributes_sha256']
            or _fingerprint(feature.attributes) != _REVIEW['attributes_sha256']):
        raise SchemaError('검토 대상 도선 원문/출처/속성/형상 변경: 새 검토가 필요합니다')
    candidates = list(islice(piers, 10001))
    if len(candidates) > 10000:
        raise SchemaError('검토용 선착장 수 상한 초과')
    output = []
    for target in _REVIEW['targets']:
        matches = [pier for pier in candidates if pier.row_number == target['row_number']]
        if len(matches) != 1:
            raise SchemaError('검토된 공식 선착장 행 누락/중복')
        pier = matches[0]
        expected_id = f"derived:20201020:{_REVIEW['pier_csv_sha256']}:{target['row_number']}"
        if (pier.source != SOURCE or pier.source_url != SOURCE_URL or pier.content_date != CONTENT_DATE
                or pier.source_sha256 != _REVIEW['pier_csv_sha256'] or pier.record_id != expected_id
                or pier.name is None or pier.name != target['name'] or pier.address != target['address']
                or not isinstance(pier.source_collected_at, datetime) or pier.source_collected_at.tzinfo is None
                or pier.source_collected_at.utcoffset() is None
                or _fingerprint(pier.raw_attributes) != target['raw_attributes_sha256']):
            raise SchemaError('검토된 선착장 원문/버전/역할 변경: 새 검토가 필요합니다')
        evidence = json.dumps({'license': _REVIEW['evidence'], 'pier_row': target['row_number'],
            'pier_csv_sha256': pier.source_sha256, 'quality': _REVIEW['quality']}, ensure_ascii=False, separators=(',', ':'))
        output.append(EndpointCrosswalk(layer.dataset_id, layer.history_date, layer.layer_id,
            feature.record_id, receipt.sha256, target['role'], pier.name, pier.source, pier.record_id,
            _REVIEW['evidence']['source_url'], evidence, _REVIEW['revision']))
    return tuple(output)
