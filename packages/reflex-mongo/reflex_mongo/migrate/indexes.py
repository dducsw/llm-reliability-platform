"""Index thường, TTL, partial unique (incidents.dedup_key), unique sli_1m {scope,key,env,ts}.

Nguồn: docs/30-data/mongodb-data-model.md §2.5 + §3 + §4 + bảng access-pattern Q1-Q12.

- TTL hot tier (`requests_ts`...) đặt ở `expireAfterSeconds` của Time
  Series (migrate/collections.py).
- TTL warm tier (`sli_1m`, `sli_1h`, `leases`) là TTL index trên trường thời gian.
- Chỉ tạo index còn thiếu (check `list_indexes()` trước), chạy lại nhiều lần không lỗi.
"""

from __future__ import annotations

from typing import Any, Final

from pymongo import IndexModel
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from reflex_mongo.collections import (
    ACTIONS,
    ATTEMPTS_TS,
    CHAOS_RUNS,
    DAY_S,
    INCIDENTS,
    INVESTIGATIONS,
    LEASES,
    POLICY_HISTORY,
    PROBES_TS,
    REPLAYS,
    REQUESTS_TS,
    SLI_1H,
    SLI_1M,
)


def _ix(*keys: tuple[str, Any], **options: Any) -> IndexModel:
    return IndexModel(list(keys), **options)


def _ttl(field: str, seconds: int) -> IndexModel:
    return _ix((field, 1), expireAfterSeconds=seconds)


# Trước 6.3 TS có sẵn {metaField, timeField}; index bên dưới chỉ thêm những gì
# query (Q9, Q12, blast radius, drill-down) thật sự cần.
INDEXES: Final[dict[str, tuple[IndexModel, ...]]] = {
    # §2.5 — blast radius theo incident (Q9); drill-down request (Console).
    # Spec ghi "sparse", nhưng server không cho sparse "$type" trên TS measurements (code 5916301);
    # acceptable: ta dùng compound index thường — được dùng cho filter `meta.route` + `ts` luôn.
    REQUESTS_TS: (_ix(("meta.route", 1), ("incident_id", 1), ("ts", 1)),),
    # §2.5 — provider rollup + Time Machine (Q12); drill-down attempt theo request
    ATTEMPTS_TS: (_ix(("meta.target", 1), ("ts", 1)), _ix(("request_id", 1))),
    # §2.5 — canary của A7/A11
    PROBES_TS: (_ix(("meta.target", 1), ("ts", 1)),),
    # §3 — Q2/Q3: unique để $merge on 4 field + TTL 45 ngày
    SLI_1M: (
        _ix(("scope", 1), ("key", 1), ("env", 1), ("ts", 1), unique=True),
        _ttl("ts", 45 * DAY_S),
    ),
    SLI_1H: (_ttl("ts", 400 * DAY_S),),
    # §4.5 — Q5/Q6
    INCIDENTS: (
        _ix(("dedup_key", 1), unique=True, partialFilterExpression={"is_open": True}),
        _ix(("key", 1), unique=True),
        _ix(("status", 1), ("t.detected_at", -1)),
        _ix(("target", 1), ("t.detected_at", -1)),
    ),
    # §4.7 — Q8/Q10
    ACTIONS: (
        _ix(("incident_id", 1), ("created_at", 1)),
        _ix(("state", 1), ("updated_at", 1)),
        _ix(("type", 1), ("verification.verdict", 1)),
    ),
    INVESTIGATIONS: (_ix(("incident_id", 1), ("run_no", 1)),),
    # rollback + Time Machine cần biết policy version tại thời điểm T
    POLICY_HISTORY: (_ix(("policy_id", 1), ("version", -1)),),
    REPLAYS: (_ix(("incident_id", 1)),),
    CHAOS_RUNS: (_ix(("active", 1)),),
    # §4.8 — TTL dự phòng để lease không bị treo nếu Sentinel chết
    LEASES: (_ttl("expires_at", DAY_S),),
}


async def ensure_indexes(db: AsyncDatabase) -> dict[str, int]:
    """Tạo index cho mọi collection trong bảng; trả về số index mới của từng collection."""
    created: dict[str, int] = {}
    for name, specs in INDEXES.items():
        collection: AsyncCollection = db[name]
        existing = {str(doc["name"]) async for doc in await collection.list_indexes()}
        missing = [ix for ix in specs if ix.document["name"] not in existing]
        if missing:
            await collection.create_indexes(missing)
            created[name] = len(missing)
    return created
