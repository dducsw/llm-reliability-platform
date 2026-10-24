"""A17 — MTTD / MTTA / MTTR theo SLI & side.

Collection: incidents
Kỹ thuật:   $percentile trên thời lượng
Spec:       docs/30-data/aggregation-catalog.md#a17
"""

from datetime import datetime
from typing import Any

ID = "A17"
COLLECTION = "incidents"


def build(
    *,
    from_: datetime,
    to: datetime,
    env: str = "local",
    sli: str | None = None,
    side: str | None = None,
) -> list[dict[str, Any]]:
    """Tính toán các KPI thời gian phản ứng sự cố: MTTD, MTTA, MTTM, MTTR theo SLI và side.

    - MTTD: detected_at − first_bad_at
    - MTTA: acknowledged_at − detected_at
    - MTTM: mitigated_at − first_bad_at
    - MTTR: resolved_at − first_bad_at
    """
    match_filter: dict[str, Any] = {
        "t.detected_at": {"$gte": from_, "$lte": to},
    }
    if env:
        match_filter["env"] = env
    if sli:
        match_filter["sli"] = sli
    if side:
        match_filter["diagnosis.side"] = side

    return [
        {"$match": match_filter},
        {
            "$set": {
                "mttd_s": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$t.first_bad_at", None]},
                                {"$ne": ["$t.detected_at", None]},
                            ]
                        },
                        {
                            "$divide": [
                                {"$subtract": ["$t.detected_at", "$t.first_bad_at"]},
                                1000,
                            ]
                        },
                        None,
                    ]
                },
                "mtta_s": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$t.acknowledged_at", None]},
                                {"$ne": ["$t.detected_at", None]},
                            ]
                        },
                        {
                            "$divide": [
                                {"$subtract": ["$t.acknowledged_at", "$t.detected_at"]},
                                1000,
                            ]
                        },
                        None,
                    ]
                },
                "mttm_s": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$t.mitigated_at", None]},
                                {"$ne": ["$t.first_bad_at", None]},
                            ]
                        },
                        {
                            "$divide": [
                                {"$subtract": ["$t.mitigated_at", "$t.first_bad_at"]},
                                1000,
                            ]
                        },
                        None,
                    ]
                },
                "mttr_s": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$t.resolved_at", None]},
                                {"$ne": ["$t.first_bad_at", None]},
                            ]
                        },
                        {
                            "$divide": [
                                {"$subtract": ["$t.resolved_at", "$t.first_bad_at"]},
                                1000,
                            ]
                        },
                        None,
                    ]
                },
            }
        },
        {
            "$group": {
                "_id": {
                    "sli": "$sli",
                    "side": "$diagnosis.side",
                },
                "count": {"$sum": 1},
                "mttd_p50": {
                    "$percentile": {
                        "input": "$mttd_s",
                        "p": [0.5, 0.9],
                        "method": "approximate",
                    }
                },
                "mtta_p50": {
                    "$percentile": {
                        "input": "$mtta_s",
                        "p": [0.5, 0.9],
                        "method": "approximate",
                    }
                },
                "mttm_p50": {
                    "$percentile": {
                        "input": "$mttm_s",
                        "p": [0.5, 0.9],
                        "method": "approximate",
                    }
                },
                "mttr_p50": {
                    "$percentile": {
                        "input": "$mttr_s",
                        "p": [0.5, 0.9],
                        "method": "approximate",
                    }
                },
                "mttd_avg": {"$avg": "$mttd_s"},
                "mttr_avg": {"$avg": "$mttr_s"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sli": "$_id.sli",
                "side": "$_id.side",
                "count": 1,
                "mttd_p50": {"$arrayElemAt": ["$mttd_p50", 0]},
                "mttd_p90": {"$arrayElemAt": ["$mttd_p50", 1]},
                "mtta_p50": {"$arrayElemAt": ["$mtta_p50", 0]},
                "mtta_p90": {"$arrayElemAt": ["$mtta_p50", 1]},
                "mttm_p50": {"$arrayElemAt": ["$mttm_p50", 0]},
                "mttm_p90": {"$arrayElemAt": ["$mttm_p50", 1]},
                "mttr_p50": {"$arrayElemAt": ["$mttr_p50", 0]},
                "mttr_p90": {"$arrayElemAt": ["$mttr_p50", 1]},
                "mttd_avg": 1,
                "mttr_avg": 1,
            }
        },
    ]
