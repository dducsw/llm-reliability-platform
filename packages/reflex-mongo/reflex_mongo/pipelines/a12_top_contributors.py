"""A12 — Top-k contributors theo chiều.

Collection: attempts_ts
Kỹ thuật:   $facet đa chiều
Spec:       docs/30-data/aggregation-catalog.md#a12
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

ID = "A12"
COLLECTION = "attempts_ts"


def build(
    *,
    target: str,
    from_: datetime,
    to: datetime,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Phân rã đa chiều các attempts lỗi để xác định nguyên nhân hàng đầu (route, finish_reason, check...)."""
    return [
        {
            "$match": {
                "meta.target": target,
                "ts": {"$gte": from_, "$lt": to},
                "outcome": {"$ne": "ok"},
            }
        },
        {
            "$facet": {
                "by_route": [
                    {"$group": {"_id": "$route", "n": {"$sum": 1}}},
                    {"$sort": {"n": -1}},
                    {"$limit": k},
                ],
                "by_outcome": [
                    {"$group": {"_id": "$outcome", "n": {"$sum": 1}}},
                    {"$sort": {"n": -1}},
                ],
                "by_finish": [
                    {"$group": {"_id": "$finish_reason", "n": {"$sum": 1}}},
                    {"$sort": {"n": -1}},
                ],
                "by_gateway": [
                    {"$group": {"_id": "$gateway_id", "n": {"$sum": 1}}},
                    {"$sort": {"n": -1}},
                ],
                "by_check": [
                    {"$unwind": "$quality.failed"},
                    {"$group": {"_id": "$quality.failed", "n": {"$sum": 1}}},
                    {"$sort": {"n": -1}},
                ],
            }
        },
    ]
