"""실제 UI DataTables 요청 계약을 쓰는 키 없는 grid 질의."""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING

from .exceptions import DownloadUnavailableError, SchemaError
from .models import LibraryResource, WebTablePage
from . import _catalog

if TYPE_CHECKING:
    from .client import VadaHubClient


async def query_table(client: VadaHubClient, resource: LibraryResource, *, start: int, page_size: int,
                      filters: dict[str,str] | None, order_by: str | None, descending: bool) -> WebTablePage:
    if (isinstance(start,bool) or not isinstance(start,int) or not 0 <= start <= 1000000
            or isinstance(page_size,bool) or not isinstance(page_size,int) or not 1 <= page_size <= 200
            or not isinstance(descending,bool)):
        raise ValueError('start 0..1000000, page_size 1..200 및 boolean 정렬 방향이 필요합니다')
    if filters is not None and (not isinstance(filters,dict) or len(filters)>200
            or not all(isinstance(key,str) and isinstance(value,str) and len(value)<=128
                       and not any(ord(c)<32 or ord(c)==127 for c in value) for key,value in filters.items())):
        raise ValueError('필터는 최대200개 column:문자열(128자)입니다')
    async with client._browser.operation() as page:
        current = await client._current_resource(page,resource)
        if not current.grid_available or current.attribute_kind not in ('SPATIAL','ATTRIBUTE'):
            raise DownloadUnavailableError('이 resource는 공개 grid를 제공하지 않습니다')
        if not re.fullmatch('[a-zA-Z][a-zA-Z0-9_]*',current.source_name):
            raise SchemaError('안전한 원천 table 이름이 아닙니다')
        schema = await client._post(page,'/user/meta/selectSankeyTableInfo.do',
                                    {'relateDtaNm':current.source_name,'gubun':'map'})
        sample, info = schema.get('tableInfo'), schema.get('schemaInfo')
        if sample == [] and info == []:
            raise DownloadUnavailableError('원천 grid에 공개된 schema/행이 없습니다')
        if (not isinstance(sample,list) or not sample or not isinstance(sample[0],dict)
                or not isinstance(info,list) or not info or len(info)>200
                or not all(isinstance(item,dict) and isinstance(item.get('attname'),str)
                           and (item.get('description') is None or isinstance(item.get('description'),str)) for item in info)):
            raise SchemaError('공개 grid schema 계약 오류')
        columns = tuple(sample[0])
        if len(columns)!=len(info) or not all(re.fullmatch('[A-Za-z][A-Za-z0-9_]*',name) for name in columns):
            raise SchemaError('공개 grid column 식별 오류')
        names = {item['attname'].replace('_','').casefold():item for item in info}
        canonical = {name.replace('_','').casefold() for name in columns}
        if len(names)!=len(info) or len(canonical)!=len(columns) or canonical != set(names):
            raise SchemaError('공개 grid schema와 JSON field가 일치하지 않습니다')
        ordered_info = [names[name.replace('_','').casefold()] for name in columns]
        if (filters and not set(filters).issubset(columns)) or (order_by is not None and order_by not in columns):
            raise ValueError('원천 schema에 없는 필터/정렬 column입니다')
        data: dict[str,str|int] = {'relateDtaNm':current.source_name,'gubun':'map','columnSize':len(columns),
            'draw':1,'start':start,'length':page_size,'search[value]':'','search[regex]':'false',
            'bsisDtaSn':current.resource_id,'maskingYn':'N','order[0][column]':columns.index(order_by) if order_by else 0,
            'order[0][dir]':'desc' if descending else 'asc'}
        for number,name in enumerate(columns):
            data.update({f'columns[{number}][data]':name,f'columns[{number}][name]':'',
                f'columns[{number}][searchable]':'true',f'columns[{number}][orderable]':'true',
                f'columns[{number}][search][value]':(filters or {}).get(name,''),
                f'columns[{number}][search][regex]':'false'})
        payload = await client._post(page,'/user/meta/selectSankeyDataTableInfo.do',data)
        # 실제 UI는 recordsTotal 대신 setRecordsTotal을 사용한다.
        total = _catalog.count(payload.get('setRecordsTotal'))
        filtered = _catalog.count(payload.get('recordsFiltered'))
        rows = payload.get('data')
        if (payload.get('draw') != 1 or isinstance(payload.get('draw'),bool) or filtered>total
                or not isinstance(rows,list) or len(rows)>page_size or len(rows)>max(0,filtered-start)
                or not all(isinstance(row,dict) and set(row)==set(columns)
                    and all(value is None or isinstance(value,(str,bool,int)) or
                            (isinstance(value,float) and math.isfinite(value)) for value in row.values()) for row in rows)):
            raise SchemaError('공개 grid 페이지/total/row 계약 오류')
        if len(rows) != min(page_size,max(0,filtered-start)):
            raise SchemaError('공개 grid가 요청 페이지를 완전히 반환하지 않았습니다')
        return WebTablePage(current,columns,tuple(item.get('description') for item in ordered_info),
                            tuple(MappingProxyType(row) for row in rows),start,page_size,total,filtered,datetime.now(timezone.utc),
                            tuple(item['attname'] for item in ordered_info))
