"""A6 — Anomaly z-score + EWMA.

Collection: sli_1m
Kỹ thuật:   $setWindowFields, $stdDevSamp, $expMovingAvg
Spec:       docs/30-data/aggregation-catalog.md#a6
"""

from datetime import datetime, timedelta
from typing import Any

ID = "A6"
COLLECTION = "sli_1m"


def build(
    *,
    now: datetime,
    scope: str = "target",
    key: str | list[str] | None = None,
    env: str = "local",
    lookback_hours: int = 3,
    recent_minutes: int = 5,
    metric_field: str = "ttft_p95",
    z_threshold: float = 3.0,
    alpha: float = 0.3,
) -> list[dict[str, Any]]:
    """Phát hiện bất thường về độ trễ/TTFT bằng z-score và EWMA qua $setWindowFields.

    Cửa sổ rolling [-60, -1] phút loại trừ phút hiện tại để tránh hiện tượng
    điểm bất thường tự kéo lệch baseline.
    """
    start_window = now - timedelta(hours=lookback_hours)
    recent_window = now - timedelta(minutes=recent_minutes)

    match_filter: dict[str, Any] = {
        "scope": scope,
        "env": env,
        "ts": {"$gte": start_window, "$lte": now},
    }
    if key:
        if isinstance(key, list):
            match_filter["key"] = {"$in": key}
        else:
            match_filter["key"] = key

    val_field = f"${metric_field}"

    return [
        {"$match": match_filter},
        {
            "$setWindowFields": {
                "partitionBy": "$key",
                "sortBy": {"ts": 1},
                "output": {
                    "mu": {
                        "$avg": val_field,
                        "window": {"range": [-60, -1], "unit": "minute"},
                    },
                    "sd": {
                        "$stdDevSamp": val_field,
                        "window": {"range": [-60, -1], "unit": "minute"},
                    },
                    "ewma": {
                        "$expMovingAvg": {"input": val_field, "alpha": alpha},
                    },
                },
            }
        },
        {"$match": {"ts": {"$gte": recent_window}}},
        {
            "$set": {
                "z": {
                    "$cond": [
                        {"$and": [{"$ne": ["$sd", None]}, {"$gt": ["$sd", 0]}]},
                        {"$divide": [{"$subtract": [val_field, "$mu"]}, "$sd"]},
                        0,
                    ]
                }
            }
        },
        {"$match": {"z": {"$gte": z_threshold}}},
        {
            "$project": {
                "_id": 0,
                "key": 1,
                "scope": 1,
                "ts": 1,
                "val": val_field,
                "mu": 1,
                "sd": 1,
                "ewma": 1,
                "z": 1,
            }
        },
        {"$sort": {"z": -1}},
    ]
