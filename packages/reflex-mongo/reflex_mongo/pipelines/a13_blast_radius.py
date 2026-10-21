"""A13 — Blast radius & chi phí của sự cố.

Collection: requests_ts
Kỹ thuật:   $group 2 tầng, $sum có điều kiện
Spec:       docs/30-data/aggregation-catalog.md#a13
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

ID = "A13"
COLLECTION = "requests_ts"


def build(
    *,
    from_: datetime,
    to: datetime,
    route: str | list[str] | None = None,
    incident_id: str | None = None,
    env: str = "local",
) -> list[dict[str, Any]]:
    """Tính toán phạm vi ảnh hưởng (blast radius), số request được Reflex cứu, và tổng chi phí thiệt hại."""
    match_filter: dict[str, Any] = {
        "ts": {"$gte": from_, "$lt": to},
    }
    if env:
        match_filter["meta.env"] = env
    if route:
        if isinstance(route, list):
            match_filter["meta.route"] = {"$in": route}
        else:
            match_filter["meta.route"] = route

    return [
        {"$match": match_filter},
        {
            "$group": {
                "_id": "$session",
                "bad": {"$sum": {"$cond": [{"$ne": ["$outcome", "ok"]}, 1, 0]}},
                "saved": {
                    "$sum": {
                        "$cond": [
                            {"$and": [{"$eq": ["$outcome", "ok"]}, {"$gt": ["$attempts", 1]}]},
                            1,
                            0,
                        ]
                    }
                },
                "reqs": {"$sum": 1},
                "cost": {"$sum": "$cost_usd"},
                "rerouted": {
                    "$sum": {
                        "$cond": [
                            {"$ne": ["$final_target", "$primary_target"]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {
            "$group": {
                "_id": None,
                "sessions": {"$sum": 1},
                "sessions_hurt": {"$sum": {"$cond": [{"$gt": ["$bad", 0]}, 1, 0]}},
                "requests": {"$sum": "$reqs"},
                "delivered_bad": {"$sum": "$bad"},
                "saved_by_reflex": {"$sum": "$saved"},
                "rerouted": {"$sum": "$rerouted"},
                "cost_usd": {"$sum": "$cost"},
            }
        },
        {"$project": {"_id": 0}},
    ]
