"""Kiểm tra expectations (incident, delivered_sli, monitor…) → báo cáo pass/fail/skip."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.sli import parse_window
from reflex_mongo.collections import INCIDENTS, SLI_1M

POLL_INTERVAL_S = 5.0
POLL_CAP_S = 300.0


def _result(exp: dict[str, Any], passed: bool | None, detail: str) -> dict[str, Any]:
    """passed=None nghĩa là không kiểm chứng được ở đây (skip), không tính là fail."""
    return {"expectation": exp, "passed": passed, "detail": detail}


async def _check_incident(
    exp: dict[str, Any], started_at: float, scale: float, db: AsyncDatabase
) -> dict[str, Any]:
    spec = exp["incident"]
    since = datetime.fromtimestamp(started_at, tz=UTC)
    query: dict[str, Any] = {"created_at": {"$gte": since}}
    if "route" in spec:
        query["routes"] = spec["route"]
    if "opened_by" in spec:
        query["source"] = spec["opened_by"]
    if "status" in spec:
        query["status"] = spec["status"]
    within_s = parse_window(exp["within"]) if "within" in exp else POLL_CAP_S
    # Trạng thái cuối (resolved) co theo scale của scenario; phát hiện thì theo cửa sổ thật của Sentinel
    if "status" in spec:
        within_s /= scale
    deadline = time.monotonic() + min(within_s, POLL_CAP_S)
    while True:
        doc = await db[INCIDENTS].find_one(query, {"key": 1})
        if doc is not None:
            return _result(exp, True, f"incident {doc.get('key')}")
        if time.monotonic() >= deadline:
            return _result(exp, False, "không có incident khớp trong thời gian chờ")
        await asyncio.sleep(POLL_INTERVAL_S)


async def _check_delivered_sli(
    exp: dict[str, Any], started_at: float, scale: float, db: AsyncDatabase
) -> dict[str, Any]:
    spec = exp["delivered_sli"]
    lo_s, hi_s = (parse_window(w) / scale for w in exp["window"])
    start = datetime.fromtimestamp(started_at, tz=UTC)
    good, total = ("q_good", "q_eligible") if spec["sli"] == "quality" else ("ok", "total")
    pipeline = [
        {
            "$match": {
                "scope": "route",
                "key": spec["route"],
                "ts": {
                    "$gte": start + timedelta(seconds=lo_s),
                    "$lt": start + timedelta(seconds=hi_s),
                },
            }
        },
        {"$group": {"_id": None, "good": {"$sum": f"${good}"}, "total": {"$sum": f"${total}"}}},
    ]
    rows = [r async for r in await db[SLI_1M].aggregate(pipeline)]
    if not rows or not rows[0]["total"]:
        return _result(exp, False, "không có dữ liệu sli_1m trong cửa sổ")
    value = rows[0]["good"] / rows[0]["total"]
    return _result(exp, value >= spec["min"], f"{spec['sli']}={value:.4f} (min {spec['min']})")


async def check(
    expectations: list[dict[str, Any]],
    started_at: float,
    *,
    db: AsyncDatabase | None = None,
    scale: float = 1.0,
) -> list[dict[str, Any]]:
    """Đánh giá expectations của scenario; trả về danh sách {expectation, passed, detail}."""
    results: list[dict[str, Any]] = []
    for exp in expectations:
        if db is None:
            results.append(_result(exp, None, "không có DB — bỏ qua"))
        elif "incident" in exp:
            results.append(await _check_incident(exp, started_at, scale, db))
        elif "delivered_sli" in exp:
            results.append(await _check_delivered_sli(exp, started_at, scale, db))
        else:
            # monitor (Datadog) và loại khác: không kiểm chứng được cục bộ
            results.append(_result(exp, None, "cần Datadog — bỏ qua"))
    return results
