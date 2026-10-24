"""공식 터미널 첨부 identity의 공통 검증."""
import re
from urllib.parse import parse_qs, urlsplit
from .exceptions import AccessDeniedError, SchemaError

NAME = '해양수산부_공동활용체계_여객터미널_20141231'


def _attachment(url: str, *, final: bool = False) -> tuple[str, str]:
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise AccessDeniedError('공식 터미널 다운로드 URL 형식 오류') from exc
    if (parts.scheme != 'https' or parts.netloc != 'www.data.go.kr' or parts.fragment
            or parts.path != '/cmm/cmm/fileDownload.do' or any(ord(c) < 32 or ord(c) == 127 for c in url)):
        raise AccessDeniedError('공식 터미널 다운로드 origin/경로가 아닙니다')
    try:
        params = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True, max_num_fields=4)
    except ValueError as exc:
        raise SchemaError('공식 터미널 첨부 인자 형식 오류') from exc
    if (not {'atchFileId', 'fileDetailSn'}.issubset(params)
            or not set(params).issubset({'atchFileId', 'fileDetailSn', 'dataNm', 'insertDataPrcus'})
            or any(len(values) != 1 for values in params.values())
            or not re.fullmatch(r'FILE_[0-9]{15}', params['atchFileId'][0])
            or not re.fullmatch(r'[1-9][0-9]{0,4}', params['fileDetailSn'][0])
            or 'insertDataPrcus' in params and params['insertDataPrcus'] != ['N']
            or 'dataNm' in params and params['dataNm'] != [NAME]
            or final and params.get('dataNm') != [NAME]):
        raise SchemaError('공식 터미널 첨부 identity/버전 인자 오류')
    return params['atchFileId'][0], params['fileDetailSn'][0]


