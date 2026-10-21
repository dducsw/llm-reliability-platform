"""A15 — Khai thác sự cố thật trong dataset.

Collection: bench_ts
Kỹ thuật:   $setWindowFields range window
Spec:       docs/30-data/aggregation-catalog.md#a15

Tìm (theo model) các giờ mà cửa sổ trượt 6h có tỉ lệ lỗi ≥ ngưỡng (mặc định 0.5),
dùng làm nguồn cho S6 (real-world-replay) và prior cho mock-llm.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

ID = "A15"
COLLECTION = "bench_ts"


def build(
    *, from_: datetime, to: datetime, threshold: float = 0.5, limit: int = 10
) -> list[dict[str, Any]]:
    """Window 6 giờ trượt trên dữ liệu hourly của mỗi model, trả về top cửa sổ lỗi dài."""
    start = from_.astimezone(UTC)
    end = to.astimezone(UTC)
    return [
        {"$match": {"ts": {"$gte": start, "$lt": end}}},
        {
            "$setWindowFields": {
                "partitionBy": "$meta.model",
                "sortBy": {"ts": 1},
                "output": {
                    "err6h": {
                        "$avg": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]},
                        "window": {"range": [-5, 0], "unit": "hour"},
                    }
                },
            }
        },
        {"$match": {"err6h": {"$gte": threshold}}},
        {
            "$group": {
                "_id": "$meta.model",
                "worst": {"$max": "$err6h"},
                "first": {"$min": "$ts"},
                "last": {"$max": "$ts"},
                "hours": {"$sum": 1},
            }
        },
        {"$sort": {"worst": -1, "hours": -1}},
        {"$limit": limit},
    ]
