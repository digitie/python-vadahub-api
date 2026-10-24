"""공식 보완 CSV→원문 보관→GDAL→터미널 참조. 신규 destination을 사용한다."""
import argparse
import asyncio
from pathlib import Path
from vadahub import OfficialTerminalClient, LocalArchiveStore, TerminalFileReceipt, terminal_to_port


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--store', type=Path, default=Path('vadahub-store'))
    parser.add_argument('--chromium')
    args = parser.parse_args()
    async with OfficialTerminalClient(timeout=60, executable_path=args.chromium) as client:
        receipt = await client.download(args.destination)
        stored = await LocalArchiveStore(args.store).put(receipt)
        assert isinstance(stored.receipt, TerminalFileReceipt)
        rows = await client.load_file(stored.receipt.local_path, receipt=stored.receipt)
        for row in rows:
            port = terminal_to_port(row)
            print(port.source, port.port_id, port.name, port.address, port.source_year)
        print('행수', len(rows), 'SHA', receipt.sha256, '원본 VadaHub SHP와 다른 공식 CSV')


if __name__ == '__main__':
    asyncio.run(main())
