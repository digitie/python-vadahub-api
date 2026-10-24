"""VadaHub 공개 UI를 이용한 T001 조사 재현 도구. provider 구현과 분리한다."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from _probe_archive import validate_archive

from playwright.async_api import async_playwright

BASE = "https://vadahub.go.kr"
TARGETS = {"관광지정보", "여객터미널", "도선항로", "여객항로"}
POST = """async ({path, data}) => {
  const r = await fetch(path, {method:'POST', redirect:'error',
    headers:{'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'},
    body:new URLSearchParams(data)});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}"""


async def probe(output: Path, executable: str | None, download: bool) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValueError("원문/receipt 혼합을 막기 위해 비어 있는 새 run 디렉터리가 필요합니다")
    output.mkdir(parents=True, exist_ok=True)
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=Path(__file__).resolve().parents[1], text=True).strip()
    report: dict = {"source_sha": source_sha, "collected_at": datetime.now(timezone.utc).isoformat(), "datasets": []}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=executable)
        try:
            page = await browser.new_page(accept_downloads=True)
            page.set_default_timeout(60000)
            await page.goto(BASE + "/renew/spaceData/index.do", wait_until="domcontentloaded")
            report["chromium"] = browser.version
            catalog = await page.evaluate(POST, {
                "path": "/renew/spaceData/list.do", "data": {"pageIndex": 1, "pageUnit": 200},
            })
            total = catalog["paginationInfo"]["totalRecordCount"]
            if total != len(catalog["resultList"]):
                raise RuntimeError("조사 페이지 상한 200을 넘었거나 카탈로그가 불완전합니다")
            selected = [r for r in catalog["resultList"] if r["metaNm"] in TARGETS]
            if len(selected) != 4 or {r["metaNm"] for r in selected} != TARGETS:
                raise RuntimeError("대상 4개 meta 계약이 달라졌습니다")
            report["catalog_total"] = total
            for dataset in selected:
                meta = str(dataset["metaSn"])
                history = dataset["histDe"]
                related = await page.evaluate(POST, {
                    "path": "/renew/selectMdMetaRelateList.do",
                    "data": {"metaSn": meta, "histDe": history},
                })
                layers = related["resultList"]
                if len(layers) != related["resultListTotCnt"] or not layers:
                    raise RuntimeError("기초자료 수량이 불일치합니다")
                record = {"meta_id": meta, "title": dataset["metaNm"], "history_date": history, "layers": []}
                report["datasets"].append(record)
                await page.goto(BASE + f"/renew/spaceData/detail.do?metaSn={meta}&histDe={history}",
                                wait_until="domcontentloaded")
                for layer in layers:
                    sid = str(layer["bsisDtaSn"])
                    if not sid.isascii() or not sid.isdecimal():
                        raise RuntimeError("안전한 숫자 layer ID가 아닙니다")
                    row = {key: layer[key] for key in (
                        "bsisDtaSn", "bsisDtaNm", "relateDtaNm", "serviceAuthCd",
                        "opnScopeSe", "gridOpenYn", "dwldPosblYn",
                    )}
                    record["layers"].append(row)
                    button = page.locator(f'button[onclick*="shpDown({sid},"]')
                    row["download_button_count"] = await button.count()
                    if layer["dwldPosblYn"] != "Y":
                        if row["download_button_count"]:
                            raise RuntimeError("미제공 상태와 다운로드 UI가 모순됩니다")
                        row["download_status"] = "unavailable"
                        continue
                    if not download:
                        row["download_status"] = "not_requested"
                        continue
                    if not row["download_button_count"]:
                        raise RuntimeError("공개 다운로드 버튼이 없습니다")
                    if not await button.first.is_visible():
                        await page.get_by_role("button", name="전체보기").click()
                    async with page.expect_download() as pending:
                        await button.first.click()
                    item = await pending.value
                    path = output / f"{sid}.zip"
                    await item.save_as(path)
                    with validate_archive(path) as archive:
                        row["members"] = archive.namelist()
                        row["member_sha256"] = {n: hashlib.sha256(archive.read(n)).hexdigest()
                                                for n in archive.namelist()}
                    with path.open("rb") as source:
                        checksum = hashlib.file_digest(source, "sha256").hexdigest()
                    row.update(download_status="downloaded", byte_size=path.stat().st_size,
                               sha256=checksum)
                    print(f"다운로드 {sid}: {row['byte_size']} bytes", flush=True)
        finally:
            await browser.close()
    report_path = output / "probe.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"조사 완료: {report_path}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/probe"))
    parser.add_argument("--executable-path")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    asyncio.run(probe(args.output_dir, args.executable_path, args.download))
