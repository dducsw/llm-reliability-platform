"""A9 — Incident signature vector 64 chiều.

Collection: sli_1m
Kỹ thuật:   $densify, $fill linear, chuẩn hóa, $concatArrays
Spec:       docs/30-data/aggregation-catalog.md#a9
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

ID = "A9"
COLLECTION = "sli_1m"


def build(
    *,
    scope: str,
    key: str,
    detected_at: datetime,
    base_p95: float = 1000.0,
    base_ttft: float = 300.0,
    env: str = "local",
) -> list[dict[str, Any]]:
    """Tạo vector biểu diễn hình dạng sự cố 64 chiều (16 phút x 4 kênh tín hiệu)."""
    start = detected_at - timedelta(minutes=12)
    end = detected_at + timedelta(minutes=4)

    match_filter: dict[str, Any] = {
        "scope": scope,
        "key": key,
        "ts": {"$gte": start, "$lt": end},
    }
    if env:
        match_filter["env"] = env

    return [
        {"$match": match_filter},
        {
            "$densify": {
                "field": "ts",
                "range": {
                    "step": 1,
                    "unit": "minute",
                    "bounds": [start, end],
                },
            }
        },
        {
            "$fill": {
                "sortBy": {"ts": 1},
                "output": {
                    "total": {"value": 0},
                    "ok": {"value": 0},
                    "q_eligible": {"value": 0},
                    "q_good": {"value": 0},
                    "p95": {"method": "linear"},
                    "ttft_p95": {"method": "linear"},
                },
            }
        },
        {
            "$set": {
                "c1": {
                    "$cond": [
                        {"$gt": ["$total", 0]},
                        {"$divide": [{"$subtract": ["$total", "$ok"]}, "$total"]},
                        0.0,
                    ]
                },
                "c2": {
                    "$cond": [
                        {"$gt": ["$q_eligible", 0]},
                        {"$divide": [{"$subtract": ["$q_eligible", "$q_good"]}, "$q_eligible"]},
                        0.0,
                    ]
                },
                "c3": {
                    "$divide": [
                        {
                            "$max": [
                                -3.0,
                                {
                                    "$min": [
                                        3.0,
                                        {
                                            "$log": [
                                                {
                                                    "$divide": [
                                                        {"$ifNull": ["$p95", base_p95]},
                                                        base_p95,
                                                    ]
                                                },
                                                2,
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                        3.0,
                    ]
                },
                "c4": {
                    "$divide": [
                        {
                            "$max": [
                                -3.0,
                                {
                                    "$min": [
                                        3.0,
                                        {
                                            "$log": [
                                                {
                                                    "$divide": [
                                                        {"$ifNull": ["$ttft_p95", base_ttft]},
                                                        base_ttft,
                                                    ]
                                                },
                                                2,
                                            ]
                                        },
                                    ]
                                },
                            ]
                        },
                        3.0,
                    ]
                },
            }
        },
        {"$sort": {"ts": 1}},
        {
            "$group": {
                "_id": None,
                "c1": {"$push": "$c1"},
                "c2": {"$push": "$c2"},
                "c3": {"$push": "$c3"},
                "c4": {"$push": "$c4"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "vec": {"$concatArrays": ["$c1", "$c2", "$c3", "$c4"]},
            }
        },
    ]
