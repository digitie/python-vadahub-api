"""실제 공식 CSV76행의 GDAL/WKT·출처·참조항구 계보."""
from datetime import date, datetime
import json
import os
from pathlib import Path
import pytest
from vadahub import OfficialTerminalClient, TerminalFileReceipt, terminal_to_port, LocalArchiveStore

pytestmark = [pytest.mark.live, pytest.mark.spatial]


async def test_live_official_terminal_geometry():
    root = Path(os.environ['VADAHUB_TERMINAL_ARTIFACTS'])
    info = json.loads((root/'terminal-receipt.json').read_text(encoding='utf-8'))
    info['local_path'] = root/info['local_path']
    info['collected_at'] = datetime.fromisoformat(info['collected_at'])
    info['content_date'] = date.fromisoformat(info['content_date'])
    receipt = TerminalFileReceipt(**info)
    store = LocalArchiveStore(root/'store')
    stored = await store.put(receipt)
    assert stored == await store.put(receipt) and await store.versions(receipt) == (stored,)
    assert isinstance(stored.receipt, TerminalFileReceipt)
    async with OfficialTerminalClient() as client:
        rows = await client.load_file(stored.receipt.local_path, receipt=stored.receipt)
    assert len(rows) == 76 and len({row.record_id for row in rows}) == 76
    assert all(row.source_sha256 == receipt.sha256 and row.source_crs is None and row.geometry_valid for row in rows)
    ports = [terminal_to_port(row) for row in rows]
    assert all(port.source == receipt.source and port.kind == 'terminal' and port.latitude is None for port in ports)
    result = {'count': len(rows), 'sha256': receipt.sha256, 'source': receipt.source, 'crs': None,
        'terminal_port_references': len(ports), 'mapped_do_seon_routes': 0, 'store_idempotent': True,
        'orphan_count': len(await store.recover())}
    (root/'terminal-gdal.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(result)
