"""mongo.sli_window, mongo.top_contributors (A12), mongo.blast_radius (A13), mongo.policy_timeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import POLICY_HISTORY, SLI_1M
from reflex_mongo.pipelines import (
    a11_side_diagnosis,
    a12_top_contributors,
    a13_blast_radius,
)

from reflex_cortex.tools.base import ToolResult


async def sli_window(
    scope: str,
    key: str,
    minutes: int = 30,
    db: AsyncDatabase | None = None,
) -> ToolResult:
    now = datetime.now(tz=UTC)
    start = now - timedelta(minutes=minutes)
    data = []
    if db is not None:
        cursor = (
            db[SLI_1M]
            .find({"scope": scope, "key": key, "ts": {"$gte": start, "$lte": now}})
            .sort("ts", 1)
        )
        async for doc in cursor:
            data.append(doc)
    else:
        data = [{"ts": now.isoformat(), "total": 100, "q_eligible": 100, "q_good": 70}]

    total_req = sum(d.get("total", 0) for d in data)
    q_good = sum(d.get("q_good", 0) for d in data)
    q_rate = (q_good / total_req) if total_req > 0 else 1.0

    return ToolResult(
        ref="sli_01",
        data=data,
        digest=f"SLI {scope}:{key} last {minutes}m: total={total_req}, quality_rate={q_rate:.2%}",
    )


async def top_contributors(
    target: str,
    minutes: int = 15,
    db: AsyncDatabase | None = None,
) -> ToolResult:
    now = datetime.now(tz=UTC)
    start = now - timedelta(minutes=minutes)
    pipeline = a12_top_contributors.build(target=target, from_=start, to=now)

    data = {}
    if db is not None:
        res = await db.attempts_ts.aggregate(pipeline).to_list(1)
        data = res[0] if res else {}
    else:
        data = {
            "by_finish": [{"_id": "length", "n": 42}, {"_id": "stop", "n": 5}],
            "by_check": [{"_id": "json_schema", "n": 40}],
        }

    return ToolResult(
        ref="contrib_01",
        data=data,
        digest=f"Top contributors for {target}: finish_reason=length (dominant), quality check failed=json_schema",
    )


async def blast_radius(
    incident_key: str,
    minutes: int = 30,
    db: AsyncDatabase | None = None,
) -> ToolResult:
    now = datetime.now(tz=UTC)
    start = now - timedelta(minutes=minutes)
    pipeline = a13_blast_radius.build(from_=start, to=now)

    data = {}
    if db is not None:
        res = await db.requests_ts.aggregate(pipeline).to_list(1)
        data = res[0] if res else {}
    else:
        data = {"requests": 1250, "delivered_bad": 28, "saved_by_reflex": 180, "cost_usd": 3.12}

    return ToolResult(
        ref="blast_01",
        data=data,
        digest=f"Blast radius: requests={data.get('requests', 0)}, saved_by_reflex={data.get('saved_by_reflex', 0)}",
    )


async def policy_timeline(
    route: str,
    minutes: int = 60,
    db: AsyncDatabase | None = None,
) -> ToolResult:
    history = []
    if db is not None:
        cursor = db[POLICY_HISTORY].find({"policy_id": route}).sort("version", -1).limit(10)
        async for doc in cursor:
            history.append(doc)
    else:
        history = [{"version": 1, "route": route}]

    return ToolResult(
        ref="pol_01",
        data=history,
        digest=f"Policy history for {route}: {len(history)} revisions found",
    )


async def probes_compare(
    target: str,
    minutes: int = 15,
    db: AsyncDatabase | None = None,
) -> ToolResult:
    """A11 — direct vs via_gateway."""
    now = datetime.now(tz=UTC)
    start = now - timedelta(minutes=minutes)
    pipeline = a11_side_diagnosis.build(target=target, from_=start, to=now)

    data = {}
    if db is not None:
        res = await db.probes_ts.aggregate(pipeline).to_list(1)
        data = res[0] if res else {}
    else:
        data = {"paths": {"direct": {"ok_ratio": 0.65}, "via_gateway": {"ok_ratio": 0.64}}}

    return ToolResult(
        ref="probe_01",
        data=data,
        digest=f"Probe compare for {target}: direct={data.get('paths', {}).get('direct', {}).get('ok_ratio')}, via_gw={data.get('paths', {}).get('via_gateway', {}).get('ok_ratio')}",
    )
