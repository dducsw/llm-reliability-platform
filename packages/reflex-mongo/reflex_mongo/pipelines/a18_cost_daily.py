"""A18 — Cost-of-reliability theo ngày (VN tz).

Collection: sli_1h
Kỹ thuật:   $dateTrunc + timezone Asia/Ho_Chi_Minh
Spec:       docs/30-data/aggregation-catalog.md#a18
"""

from datetime import datetime
from typing import Any

ID = "A18"
COLLECTION = "sli_1h"


def build(
    *,
    from_: datetime,
    to: datetime,
    env: str = "local",
    scope: str | None = None,
    timezone: str = "Asia/Ho_Chi_Minh",
) -> list[dict[str, Any]]:
    """Gom toàn bộ chi phí token và độ tin cậy theo từng ngày dương lịch chuẩn múi giờ Asia/Ho_Chi_Minh.

    Tổng hợp tokens in/out, chi phí USD, số lượng request và số lần retry/hedge phục vụ báo cáo.
    """
    match_filter: dict[str, Any] = {
        "ts": {"$gte": from_, "$lt": to},
    }
    if env:
        match_filter["env"] = env
    if scope:
        match_filter["scope"] = scope

    return [
        {"$match": match_filter},
        {
            "$group": {
                "_id": {
                    "day": {
                        "$dateTrunc": {
                            "date": "$ts",
                            "unit": "day",
                            "timezone": timezone,
                        }
                    },
                    "scope": "$scope",
                },
                "cost_usd": {"$sum": "$cost_usd"},
                "tokens_in": {"$sum": "$tokens_in"},
                "tokens_out": {"$sum": "$tokens_out"},
                "total_requests": {"$sum": "$total"},
                "retries": {"$sum": "$retries"},
                "hedges": {"$sum": "$hedges"},
            }
        },
        {"$sort": {"_id.day": 1, "_id.scope": 1}},
        {
            "$project": {
                "_id": 0,
                "day": "$_id.day",
                "scope": "$_id.scope",
                "cost_usd": 1,
                "tokens_in": 1,
                "tokens_out": 1,
                "total_requests": 1,
                "retries": 1,
                "hedges": 1,
            }
        },
    ]
