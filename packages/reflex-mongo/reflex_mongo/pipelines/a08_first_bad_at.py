"""A8 — First-bad-at (cho MTTD).

Collection: sli_1m
Kỹ thuật:   $setWindowFields ($shift)
Spec:       docs/30-data/aggregation-catalog.md#a8
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

ID = "A8"
COLLECTION = "sli_1m"


def build(
    *,
    scope: str,
    key: str,
    detected_at: datetime,
    budget: float = 0.01,
    lookback_hours: int = 1,
) -> list[dict[str, Any]]:
    """Xác định thời điểm đầu tiên tỷ lệ lỗi vượt ngưỡng trước khi alert được phát hiện."""
    window_start = detected_at - timedelta(hours=lookback_hours)
    error_threshold = budget * 2.0

    return [
        {
            "$match": {
                "scope": scope,
                "key": key,
                "ts": {"$gte": window_start, "$lte": detected_at},
            }
        },
        {
            "$set": {
                "bad": {
                    "$gt": [
                        {
                            "$divide": [
                                {"$subtract": ["$q_eligible", "$q_good"]},
                                {"$max": ["$q_eligible", 1]},
                            ]
                        },
                        error_threshold,
                    ]
                }
            }
        },
        {
            "$setWindowFields": {
                "sortBy": {"ts": 1},
                "output": {
                    "prev_bad": {
                        "$shift": {
                            "output": "$bad",
                            "by": -1,
                            "default": False,
                        }
                    }
                },
            }
        },
        {
            "$match": {
                "bad": True,
                "prev_bad": False,
            }
        },
        {"$sort": {"ts": -1}},
        {"$limit": 1},
    ]
