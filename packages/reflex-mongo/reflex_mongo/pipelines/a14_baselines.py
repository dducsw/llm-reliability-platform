"""A14 — Baseline hour-of-week từ dataset public.

Collection: bench_ts → baselines
Kỹ thuật:   $dateToParts, $median, $merge
Spec:       docs/30-data/aggregation-catalog.md#a14

Output shape (`baselines`): {_id: {model, dow, hour},
lat_median, lat_p90, ttft_median, err_ratio, samples, updated_at}.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

ID = "A14"
COLLECTION = "bench_ts"


def build(*, days: int = 60, now: datetime | None = None) -> list[dict[str, Any]]:
    """Pipeline quét `days` ngày gần nhất, group theo (model, thứ, giờ)."""
    start = (now or datetime.now(tz=UTC)).replace(minute=0, second=0, microsecond=0) - timedelta(
        days=days
    )
    return [
        {"$match": {"ts": {"$gte": start}}},
        {
            "$set": {
                # UTC: peak theo giờ US/EU
                "p": {"$dateToParts": {"date": "$ts"}},
                "dow": {"$isoDayOfWeek": "$ts"},
            }
        },
        {
            "$group": {
                "_id": {"model": "$meta.model", "dow": "$dow", "hour": "$p.hour"},
                "lat_median": {"$median": {"input": "$latency_ms", "method": "approximate"}},
                "lat_p90": {
                    "$percentile": {"input": "$latency_ms", "p": [0.9], "method": "approximate"}
                },
                "ttft_median": {"$median": {"input": "$ttft_ms", "method": "approximate"}},
                "err_ratio": {"$avg": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
                "samples": {"$sum": 1},
            }
        },
        {
            "$set": {
                "lat_p90": {"$arrayElemAt": ["$lat_p90", 0]},
                "updated_at": "$$NOW",
            }
        },
        # baselines: median/p90 theo hour-of-week của từng model
        {"$merge": {"into": "baselines", "on": "_id", "whenMatched": "replace"}},
    ]
