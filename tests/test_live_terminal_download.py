"""공식 공개 버튼을 실제 클릭한 터미널 보완 CSV 다운로드."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import pytest
from vadahub import OfficialTerminalClient

pytestmark = pytest.mark.live


async def test_live_official_terminal_file(tmp_path):
    root = Path(os.environ.get('VADAHUB_TERMINAL_ARTIFACTS', str(tmp_path)))
    root.mkdir(parents=True, exist_ok=True)
    async with OfficialTerminalClient(timeout=60, executable_path=os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')) as client:
        receipt = await client.download(root/'terminal.csv')
        data = asdict(receipt)
        data.update(collected_at=receipt.collected_at.isoformat(), content_date=receipt.content_date.isoformat(),
            local_path=receipt.local_path.name)
        assert receipt.source == 'data.go.kr:15148558' and receipt.byte_size > 0
        with pytest.raises(FileExistsError): await client.download(receipt.local_path)
    (root/'terminal-receipt.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(data)
