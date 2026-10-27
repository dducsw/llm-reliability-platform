"""SE-9.3 — `task demo:reset`: đưa môi trường demo về trạng thái sạch giữa các lần quay.

Xoá trạng thái runtime (incident/action/investigation/postmortem do demo tạo, replays, chaos_runs,
outbox, health_state) nhưng GIỮ Incident Memory bootstrap (`synthetic: true`) và dữ liệu
time series. Policy về lại seed với `version` tăng tiếp (không lùi version → gateway và
policy_history vẫn nhất quán).

Mặc định chỉ in số document sẽ xoá; thêm `--yes` để thực hiện.

    uv run python tools/demo_reset.py           # dry-run
    uv run python tools/demo_reset.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pymongo import AsyncMongoClient
from reflex_mongo.collections import (
    ACTIONS,
    CHAOS_RUNS,
    HEALTH_STATE,
    INCIDENTS,
    INVESTIGATIONS,
    OUTBOX,
    POLICIES,
    POLICY_HISTORY,
    POSTMORTEMS,
    REPLAYS,
)

NOT_BOOTSTRAP = {"synthetic": {"$ne": True}}
PLAN: list[tuple[str, dict[str, Any]]] = [
    (INCIDENTS, NOT_BOOTSTRAP),
    (ACTIONS, {"_id": {"$not": {"$regex": "^act-INC-HIST-"}}}),
    (INVESTIGATIONS, {}),
    (POSTMORTEMS, {"incident_id": {"$not": {"$regex": "^INC-HIST-"}}}),
    (REPLAYS, {}),
    (CHAOS_RUNS, {}),
    (OUTBOX, {}),
    (HEALTH_STATE, {}),
]


async def reset(db: Any, seeds: Path, apply: bool) -> dict[str, Any]:
    report: dict[str, Any] = {"deleted": {}, "policies": {}}
    for coll, flt in PLAN:
        if apply:
            report["deleted"][coll] = (await db[coll].delete_many(flt)).deleted_count
        else:
            report["deleted"][coll] = await db[coll].count_documents(flt)

    now = datetime.now(tz=UTC)
    for doc in yaml.safe_load((seeds / "policies.yaml").read_text(encoding="utf-8")):
        current = await db[POLICIES].find_one({"_id": doc["_id"]})
        version = (current or {}).get("version", 0) + 1
        report["policies"][doc["_id"]] = version
        if not apply:
            continue
        if current:
            await db[POLICY_HISTORY].insert_one(
                {"policy_id": doc["_id"], "version": current["version"], "doc": current, "at": now}
            )
        new = {
            **doc,
            "version": version,
            "updated_at": now,
            "updated_by": {"actor": "demo_reset", "reason": "demo_reset"},
        }
        await db[POLICIES].replace_one({"_id": doc["_id"]}, new, upsert=True)
    return report


async def main_async(apply: bool, seeds: Path) -> dict[str, Any]:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        sys.exit("MONGODB_URI chưa đặt (task tự nạp .env).")
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(uri)
    try:
        db = client[os.environ.get("MONGODB_DB", "reflex")]
        return await reset(db, seeds, apply)
    finally:
        await client.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--yes", action="store_true", help="thực sự xoá (mặc định dry-run)")
    ap.add_argument("--seeds", type=Path, default=Path("seeds"))
    args = ap.parse_args()
    if os.environ.get("REFLEX_ENV") == "prod":
        sys.exit("Từ chối reset khi REFLEX_ENV=prod.")
    report = asyncio.run(main_async(args.yes, args.seeds))
    mode = "ĐÃ XOÁ" if args.yes else "DRY-RUN (thêm --yes để thực hiện)"
    print(mode)
    for coll, n in report["deleted"].items():
        print(f"  {coll:<16} {n}")
    for pid, v in report["policies"].items():
        print(f"  policy {pid:<16} → seed, v{v}")


if __name__ == "__main__":
    main()
