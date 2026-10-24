"""A7 — Probe blindness (mất tín hiệu).

Collection: probes_ts
Kỹ thuật:   $densify, $fill
Spec:       docs/30-data/aggregation-catalog.md#a7
"""

from datetime import datetime, timedelta
from typing import Any

ID = "A7"
COLLECTION = "probes_ts"


def build(
    *,
    now: datetime,
    env: str = "local",
    lookback_minutes: int = 10,
    target: str | None = None,
) -> list[dict[str, Any]]:
    """Phát hiện probe blindness (mất toàn bộ tín hiệu canary probe) qua $densify + $fill.

    Nếu trong lookback_minutes phút liên tiếp một đường probe (target, path)
    không gửi bất kỳ mẫu đo nào về, đánh dấu sự cố probe blindness.
    """
    now_minute = now.replace(second=0, microsecond=0)
    start_window = (now - timedelta(minutes=lookback_minutes)).replace(second=0, microsecond=0)

    match_filter: dict[str, Any] = {
        "meta.env": env,
        "ts": {"$gte": start_window, "$lt": now_minute},
    }
    if target:
        match_filter["meta.target"] = target

    return [
        {"$match": match_filter},
        {
            "$group": {
                "_id": {
                    "target": "$meta.target",
                    "path": "$meta.path",
                    "ts": {"$dateTrunc": {"date": "$ts", "unit": "minute"}},
                },
                "n": {"$sum": 1},
            }
        },
        {
            "$replaceWith": {
                "target": "$_id.target",
                "path": "$_id.path",
                "ts": "$_id.ts",
                "n": "$n",
            }
        },
        {
            "$densify": {
                "field": "ts",
                "partitionByFields": ["target", "path"],
                "range": {
                    "step": 1,
                    "unit": "minute",
                    "bounds": [start_window, now_minute],
                },
            }
        },
        {"$fill": {"output": {"n": {"value": 0}}}},
        {"$match": {"n": 0}},
        {
            "$group": {
                "_id": {"target": "$target", "path": "$path"},
                "silent_minutes": {"$sum": 1},
            }
        },
        {
            "$project": {
                "_id": 0,
                "target": "$_id.target",
                "path": "$_id.path",
                "silent_minutes": 1,
            }
        },
        {"$sort": {"silent_minutes": -1}},
    ]
