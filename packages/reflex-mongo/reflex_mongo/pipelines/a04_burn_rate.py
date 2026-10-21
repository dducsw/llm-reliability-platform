"""A4 — Multi-window burn rate trong một lần quét.

Collection: sli_1m
Kỹ thuật:   conditional $sum
Spec:       docs/30-data/aggregation-catalog.md#a4
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

ID = "A4"
COLLECTION = "sli_1m"


def build(
    *,
    now: Any,
    scope: str = "target",
    keys: list[str] | None = None,
    env: str = "local",
    short_window_s: int = 30,
    long_window_s: int = 180,
    max_window_s: int = 6 * 3600,
) -> list[dict[str, Any]]:
    start_max = now - timedelta(seconds=max_window_s)
    start_long = now - timedelta(seconds=long_window_s)
    start_short = now - timedelta(seconds=short_window_s)

    match_stage: dict[str, Any] = {
        "scope": scope,
        "ts": {"$gte": start_max, "$lte": now},
    }
    if keys:
        match_stage["key"] = {"$in": keys}

    return [
        {"$match": match_stage},
        {
            "$group": {
                "_id": "$key",
                "t_short": {"$sum": {"$cond": [{"$gte": ["$ts", start_short]}, "$total", 0]}},
                "b_short": {
                    "$sum": {
                        "$cond": [
                            {"$gte": ["$ts", start_short]},
                            {"$subtract": ["$total", "$ok"]},
                            0,
                        ]
                    }
                },
                "q_elig_short": {
                    "$sum": {"$cond": [{"$gte": ["$ts", start_short]}, "$q_eligible", 0]}
                },
                "q_good_short": {
                    "$sum": {"$cond": [{"$gte": ["$ts", start_short]}, "$q_good", 0]}
                },
                "t_long": {"$sum": {"$cond": [{"$gte": ["$ts", start_long]}, "$total", 0]}},
                "b_long": {
                    "$sum": {
                        "$cond": [
                            {"$gte": ["$ts", start_long]},
                            {"$subtract": ["$total", "$ok"]},
                            0,
                        ]
                    }
                },
                "q_elig_long": {
                    "$sum": {"$cond": [{"$gte": ["$ts", start_long]}, "$q_eligible", 0]}
                },
                "q_good_long": {
                    "$sum": {"$cond": [{"$gte": ["$ts", start_long]}, "$q_good", 0]}
                },
                "t_total": {"$sum": "$total"},
                "b_total": {"$sum": {"$subtract": ["$total", "$ok"]}},
            }
        },
        {
            "$project": {
                "key": "$_id",
                "t_short": 1,
                "b_short": 1,
                "t_long": 1,
                "b_long": 1,
                "q_elig_short": 1,
                "q_good_short": 1,
                "q_elig_long": 1,
                "q_good_long": 1,
                "t_total": 1,
                "b_total": 1,
            }
        },
    ]
