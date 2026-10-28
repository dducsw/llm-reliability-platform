"""A16 — Recovery Proof data (trước/sau).

Collection: sli_1m
Kỹ thuật:   $facet trước/sau
Spec:       docs/30-data/aggregation-catalog.md#a16
"""

from datetime import datetime
from typing import Any

ID = "A16"
COLLECTION = "sli_1m"


def build(
    *,
    key: str,
    scope: str = "route",
    baseline: tuple[datetime, datetime] | dict[str, datetime] | None = None,
    after: tuple[datetime, datetime] | dict[str, datetime] | None = None,
    base_from: datetime | None = None,
    base_to: datetime | None = None,
    after_from: datetime | None = None,
    after_to: datetime | None = None,
    env: str = "local",
) -> list[dict[str, Any]]:
    """Tổng hợp dữ liệu trước và sau khi kích hoạt action nhằm kiểm định hồi phục (Recovery Proof).

    Dùng $facet để chia đôi cửa sổ dữ liệu (baseline vs after), trả về số mẫu và histogram độ trễ
    làm đầu vào cho kiểm định Wilson CI và two-proportion z-test tại RecoveryVerifier.
    """
    if baseline is not None:
        if isinstance(baseline, (tuple, list)) and len(baseline) == 2:
            base_from, base_to = baseline[0], baseline[1]
        elif isinstance(baseline, dict):
            base_from, base_to = baseline["from"], baseline["to"]

    if after is not None:
        if isinstance(after, (tuple, list)) and len(after) == 2:
            after_from, after_to = after[0], after[1]
        elif isinstance(after, dict):
            after_from, after_to = after["from"], after["to"]

    if base_from is None or base_to is None or after_from is None or after_to is None:
        raise ValueError("Both baseline and after windows (from and to) must be specified.")

    return [
        {
            "$match": {
                "scope": scope,
                "key": key,
                "env": env,
                "ts": {"$gte": base_from, "$lt": after_to},
            }
        },
        {
            "$facet": {
                "baseline": [
                    {"$match": {"ts": {"$gte": base_from, "$lt": base_to}}},
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": "$total"},
                            "ok": {"$sum": "$ok"},
                            "q_eligible": {"$sum": "$q_eligible"},
                            "q_good": {"$sum": "$q_good"},
                            "lh": {"$push": "$lat_hist"},
                        }
                    },
                ],
                "after": [
                    {"$match": {"ts": {"$gte": after_from, "$lt": after_to}}},
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": "$total"},
                            "ok": {"$sum": "$ok"},
                            "q_eligible": {"$sum": "$q_eligible"},
                            "q_good": {"$sum": "$q_good"},
                            "lh": {"$push": "$lat_hist"},
                        }
                    },
                ],
            }
        },
    ]
