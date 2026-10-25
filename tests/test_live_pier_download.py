"""공식 선착장 CSV를 실제 Chromium 공개 버튼에서 새로 받는다."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import pytest
from vadahub import OfficialPierClient, pier_to_port

pytestmark = pytest.mark.live


async def test_live_official_pier_download(tmp_path):
    root = Path(os.environ.get('VADAHUB_PIER_ARTIFACTS', str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    async with OfficialPierClient(timeout=90, executable_path=os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')) as client:
        receipt = await client.download(root/'piers.csv')
        rows = await client.load_file(receipt.local_path, receipt=receipt)
        assert len(rows) == 340 and len({r.record_id for r in rows}) == 340
        assert rows[83].name == '외동' and rows[84].name == '국동'
        assert rows[83].raw_attributes['도선기착지유무'] == 'N'
        assert rows[84].raw_attributes['도선기착지유무'] == ''
        assert all(pier_to_port(r).latitude is None for r in rows if r.name)
    report = asdict(receipt); report['rows'] = len(rows)
    (root/'pier-live.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, default=str))
