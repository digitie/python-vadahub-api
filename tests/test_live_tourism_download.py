"""현재 registry로 찾은 관광 9종의 실제 공개 버튼 다운로드."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import pytest
from vadahub import VadaHubFileClient, TOURISM_SOURCES

pytestmark = pytest.mark.live


async def test_live_tourism_nine_downloads(tmp_path):
    root = Path(os.environ.get('VADAHUB_TOURISM_ARTIFACTS', str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    receipts = []
    async with VadaHubFileClient(timeout=120, executable_path=os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')) as client:
        selected = await client.list_tourism_layers()
        assert len(selected) == len(TOURISM_SOURCES) == 9
        for item in selected:
            receipt = await client.download(item.layer, root / (item.source.category + '.zip'))
            record = asdict(receipt)
            record.update(category=item.source.category, local_path=receipt.local_path.name,
                collected_at=receipt.collected_at.isoformat())
            receipts.append(record)
            (root / 'tourism-receipts.json').write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding='utf-8')
            print(item.source.category, receipt.byte_size, receipt.sha256, flush=True)
    assert len(receipts) == 9 and all(len(r['member_sha256']) == 4 for r in receipts)
