"""Chuỗi thời gian cho Pulse: Delivered (scope=route) vs Provider (scope=target) từ sli_1m."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query, Request
from reflex_mongo.collections import POLICIES, POLICY_HISTORY, SLI_1M

router = APIRouter()

_COUNTERS = ("total", "ok", "q_eligible", "q_good")


def sum_by_minute(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cộng các counter theo phút (nhiều target của cùng một route → một đường Provider)."""
    acc: dict[Any, dict[str, int]] = defaultdict(lambda: dict.fromkeys(_COUNTERS, 0))
    for d in docs:
        for c in _COUNTERS:
            acc[d["ts"]][c] += int(d.get(c, 0))
    return [{"ts": ts, **vals} for ts, vals in sorted(acc.items(), key=lambda kv: kv[0])]


async def _series(db: Any, scope: str, keys: list[str], since: datetime) -> list[dict[str, Any]]:
    cursor = db[SLI_1M].find({"scope": scope, "key": {"$in": keys}, "ts": {"$gte": since}})
    return sum_by_minute([d async for d in cursor])


@router.get("/api/series/dual")
async def dual_ledger(
    request: Request,
    route: str,
    minutes: int = Query(60, ge=5, le=1440),
) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"route": route, "targets": [], "delivered": [], "provider": [], "events": []}

    since = datetime.now(tz=UTC) - timedelta(minutes=minutes)
    policy = await db[POLICIES].find_one({"_id": route})
    targets = [c["target"] for c in (policy or {}).get("candidates", [])]

    delivered = await _series(db, "route", [route], since)
    provider = await _series(db, "target", targets, since) if targets else []

    # policy_history lưu snapshot của version cũ tại thời điểm đổi → version mới = version + 1.
    events = [
        {"ts": h["at"], "kind": "policy", "label": f"v{h['version'] + 1}"}
        async for h in db[POLICY_HISTORY].find({"policy_id": route, "at": {"$gte": since}})
    ]
    return {
        "route": route,
        "targets": targets,
        "delivered": delivered,
        "provider": provider,
        "events": sorted(events, key=lambda e: e["ts"]),
    }
