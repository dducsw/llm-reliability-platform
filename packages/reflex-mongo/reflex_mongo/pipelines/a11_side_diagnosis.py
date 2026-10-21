"""A11 — Chẩn đoán phân biệt: provider hay gateway.

Collection: probes_ts
Kỹ thuật:   $group theo meta.path
Spec:       docs/30-data/aggregation-catalog.md#a11
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

ID = "A11"
COLLECTION = "probes_ts"


def build(
    *,
    target: str,
    from_: datetime,
    to: datetime,
    env: str = "local",
) -> list[dict[str, Any]]:
    """So sánh chất lượng probe đường direct vs via_gateway để phân biệt lỗi provider hay gateway."""
    match_filter: dict[str, Any] = {
        "meta.target": target,
        "ts": {"$gte": from_, "$lte": to},
    }
    if env:
        match_filter["meta.env"] = env

    return [
        {"$match": match_filter},
        {
            "$group": {
                "_id": "$meta.path",
                "n": {"$sum": 1},
                "ok": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": ["$outcome", "ok"]},
                                    {"$eq": ["$quality.pass", True]},
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
                "p95": {
                    "$percentile": {
                        "input": "$latency_ms",
                        "p": [0.95],
                        "method": "approximate",
                    }
                },
            }
        },
        {
            "$group": {
                "_id": None,
                "paths": {
                    "$push": {
                        "k": "$_id",
                        "v": {
                            "ok_ratio": {"$divide": ["$ok", "$n"]},
                            "p95": {"$first": "$p95"},
                        },
                    }
                },
            }
        },
        {"$project": {"_id": 0, "paths": {"$arrayToObject": "$paths"}}},
    ]
