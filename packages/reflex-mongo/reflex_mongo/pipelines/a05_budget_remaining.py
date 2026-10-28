"""A5 — Error budget còn lại.

Collection: sli_1h ∪ sli_1m
Kỹ thuật:   $unionWith
Spec:       docs/30-data/aggregation-catalog.md#a5
"""

from datetime import datetime, timedelta
from typing import Any

ID = "A5"
COLLECTION = "sli_1h"


def build(
    *,
    now: datetime,
    scope: str = "target",
    key: str = "vendorA:large",
    budget: float = 0.01,
    slo: Any = None,
    window_start: datetime | None = None,
    env: str = "local",
) -> list[dict[str, Any]]:
    """Xây dựng pipeline tính toán Error Budget còn lại bằng cách nối sli_1h và sli_1m.

    - sli_1h: Lịch sử các giờ đã hoàn tất từ window_start đến đầu giờ hiện tại.
    - sli_1m: Các phút đang tích lũy của giờ hiện tại.
    """
    if slo is not None:
        if isinstance(slo, (int, float)):
            budget = float(slo)
        elif hasattr(slo, "objective"):
            budget = 1.0 - float(slo.objective)
            scope = getattr(slo, "scope", scope)
            key = getattr(slo, "key", key)
        elif isinstance(slo, dict):
            if "objective" in slo:
                budget = 1.0 - float(slo["objective"])
            elif "budget" in slo:
                budget = float(slo["budget"])
            scope = slo.get("scope", scope)
            key = slo.get("key", key)

    current_hour = now.replace(minute=0, second=0, microsecond=0)
    if window_start is None:
        window_start = now - timedelta(days=30)

    return [
        {
            "$match": {
                "scope": scope,
                "key": key,
                "env": env,
                "ts": {"$gte": window_start, "$lt": current_hour},
            }
        },
        {
            "$unionWith": {
                "coll": "sli_1m",
                "pipeline": [
                    {
                        "$match": {
                            "scope": scope,
                            "key": key,
                            "env": env,
                            "ts": {"$gte": current_hour, "$lte": now},
                        }
                    }
                ],
            }
        },
        {
            "$group": {
                "_id": None,
                "total": {"$sum": "$total"},
                "ok": {"$sum": "$ok"},
                "bad": {"$sum": {"$subtract": ["$total", "$ok"]}},
                "q_eligible": {"$sum": "$q_eligible"},
                "q_good": {"$sum": "$q_good"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "total": 1,
                "ok": 1,
                "bad": 1,
                "sli": {
                    "$cond": [
                        {"$gt": ["$total", 0]},
                        {"$subtract": [1, {"$divide": ["$bad", "$total"]}]},
                        1.0,
                    ]
                },
                "allowed_bad": {"$multiply": ["$total", budget]},
                "remaining": {
                    "$cond": [
                        {"$gt": [{"$multiply": ["$total", budget]}, 0]},
                        {
                            "$subtract": [
                                1,
                                {"$divide": ["$bad", {"$multiply": ["$total", budget]}]},
                            ]
                        },
                        1.0,
                    ]
                },
            }
        },
    ]
