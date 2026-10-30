"""Ghi id SLO/monitor Datadog (Terraform output `mongo_slo_links`) vào `slos.datadog` (T7).

`reflex-mongo seed` ghi đè cả document `slos` (replace theo `_id`) → chạy lại script này sau mỗi lần seed.
Chỉ `$set` field `datadog` theo đúng `_id`; `_id` không có trong collection thì báo, không tạo mới.

    uv run python tools/sync_datadog_ids.py            # dry-run
    uv run python tools/sync_datadog_ids.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from pymongo import AsyncMongoClient
from reflex_mongo.collections import SLOS

TF_DIR = Path(__file__).resolve().parents[1] / "infra" / "terraform"


def terraform_links(tf_dir: Path = TF_DIR) -> dict[str, dict[str, Any]]:
    out = subprocess.run(
        ["terraform", f"-chdir={tf_dir}", "output", "-json", "mongo_slo_links"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def updates(links: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """(`_id` trong `slos`, giá trị field `datadog`)."""
    return [
        (slo, {"slo_id": str(v["slo_id"]), "monitor_ids": [str(m) for m in v["monitor_ids"]]})
        for slo, v in sorted(links.items())
    ]


async def sync(db: Any, links: dict[str, dict[str, Any]], apply: bool) -> dict[str, str]:
    report: dict[str, str] = {}
    for slo, dd in updates(links):
        if await db[SLOS].count_documents({"_id": slo}) == 0:
            report[slo] = "missing"
            continue
        if apply:
            await db[SLOS].update_one({"_id": slo}, {"$set": {"datadog": dd}})
        report[slo] = f"slo_id={dd['slo_id']} monitors={len(dd['monitor_ids'])}"
    return report


async def main_async(apply: bool) -> dict[str, str]:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        sys.exit("MONGODB_URI chưa đặt (task tự nạp .env).")
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(uri)
    try:
        db = client[os.environ.get("MONGODB_DB", "reflex")]
        return await sync(db, terraform_links(), apply)
    finally:
        await client.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--yes", action="store_true", help="ghi thật (mặc định dry-run)")
    args = ap.parse_args()
    report = asyncio.run(main_async(args.yes))
    print("APPLIED" if args.yes else "DRY-RUN (thêm --yes để ghi)")
    for slo, line in report.items():
        print(f"  {slo:<32} {line}")


if __name__ == "__main__":
    main()
