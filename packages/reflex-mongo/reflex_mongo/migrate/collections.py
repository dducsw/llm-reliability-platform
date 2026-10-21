"""Tạo Time Series + collection thường (bỏ qua nếu đã tồn tại). Idempotent.

- TS: {"timeField": "ts", "metaField": "meta", "granularity": theo bảng} +
  `expireAfterSeconds` (TTL) khi cấu hình — bench_ts là reference nên không TTL.
- Mọi collection được tạo bằng `db.command("create", ...)` để truyền option đầy đủ.
"""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase

from reflex_mongo.collections import (
    ACTIONS,
    BASELINES,
    CHAOS_RUNS,
    HEALTH_STATE,
    INCIDENTS,
    INVESTIGATIONS,
    LEASES,
    OUTBOX,
    POLICIES,
    POLICY_HISTORY,
    POSTMORTEMS,
    REPLAYS,
    SLI_1H,
    SLI_1M,
    SLOS,
    STREAM_CHECKPOINTS,
    TARGETS,
    TIMESERIES,
)

REGULARS: tuple[str, ...] = (
    SLI_1M,
    SLI_1H,
    BASELINES,
    TARGETS,
    SLOS,
    POLICIES,
    POLICY_HISTORY,
    HEALTH_STATE,
    INCIDENTS,
    INVESTIGATIONS,
    ACTIONS,
    POSTMORTEMS,
    REPLAYS,
    CHAOS_RUNS,
    OUTBOX,
    STREAM_CHECKPOINTS,
    LEASES,
)


async def ensure_collections(db: AsyncDatabase) -> None:
    existing = {doc["name"] async for doc in await db.list_collections()}

    for name, config in TIMESERIES.items():
        if name in existing:
            continue
        cmd: dict[str, object] = {
            "create": name,
            "timeseries": {
                "timeField": "ts",
                "metaField": "meta",
                "granularity": config["granularity"],
            },
        }
        if config["ttl_s"] is not None:
            cmd["expireAfterSeconds"] = config["ttl_s"]  # type: ignore[assignment]
        await db.command(cmd)

    for name in REGULARS:
        if name in existing:
            continue
        await db.command({"create": name})
