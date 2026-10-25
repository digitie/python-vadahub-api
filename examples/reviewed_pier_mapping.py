"""설치본의 실제 선착장CSV·도선SHP 수집→보관→GDAL→검토된 두 시설 연결."""
import argparse
import asyncio
import json
import os
from pathlib import Path
from vadahub import (OfficialPierClient, VadaHubFileClient, LocalArchiveStore,
    pier_to_port, reviewed_route_crosswalks, map_route)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='신규 원문·보관 경로')
    args = parser.parse_args()
    root = args.directory.absolute(); root.mkdir(parents=True, exist_ok=False)
    chromium = os.environ.get('VADAHUB_CHROMIUM_EXECUTABLE')
    store = LocalArchiveStore(root/'store')
    async with OfficialPierClient(timeout=90, executable_path=chromium) as client:
        receipt = await client.download(root/'piers.csv')
        stored = await store.put(receipt)
        assert isinstance(stored.receipt, type(receipt))
        piers = await client.load_file(stored.receipt.local_path, receipt=stored.receipt)
    async with VadaHubFileClient(timeout=90, executable_path=chromium) as client:
        dataset = next(d for d in await client.list_datasets() if d.dataset_id == '52')
        layer = next(l for l in await client.list_layers(dataset) if l.layer_id == '500048')
        archive = await client.download(layer, root/'route.zip')
        await store.put(archive)
        features = await client.load_file(archive.local_path, layer=archive.layer, receipt=archive)
    ports = [pier_to_port(p) for p in piers if p.name]
    mapped = []
    for feature in features:
        crosswalk = reviewed_route_crosswalks(feature, receipt=archive, piers=piers)
        if not crosswalk:
            continue
        result = map_route(feature, ports=ports, crosswalk=crosswalk, endpoint_kind='pier')
        assert result.departure.port and result.arrival.port
        mapped.append({'record': feature.record_id,
            'departure': {'key': result.departure.port.key, 'name': result.departure.port.name,
                'address': result.departure.port.address},
            'arrival': {'key': result.arrival.port.key, 'name': result.arrival.port.name,
                'address': result.arrival.port.address}, 'revision': crosswalk[0].revision})
    assert len(mapped) == 1 and len(features) == 34 and len(piers) == 340
    print(json.dumps({'mapped': mapped, 'unresolved': len(features)-len(mapped), 'pier_rows': len(piers),
        'pier_sha256': receipt.sha256, 'archive_sha256': archive.sha256}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
