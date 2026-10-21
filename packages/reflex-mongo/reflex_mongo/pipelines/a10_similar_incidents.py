"""A10 — Sự cố tương tự + hiệu quả action.

Collection: incidents ⨝ actions
Kỹ thuật:   $vectorSearch, $lookup, $median
Spec:       docs/30-data/aggregation-catalog.md#a10
"""

from __future__ import annotations

from typing import Any

ID = "A10"
COLLECTION = "incidents"


def build(
    *,
    vec: list[float],
    sli: str,
    scope: str | None = None,
    k: int = 10,
    current_id: str | None = None,
    min_similarity: float = 0.70,
) -> list[dict[str, Any]]:
    """Tìm kiếm sự cố tương đồng qua Atlas Vector Search và thống kê tỷ lệ thành công của các hành động khắc phục."""
    search_filter: dict[str, Any] = {
        "status": "resolved",
        "signature.v": 2,
        "sli": sli,
    }
    if scope:
        search_filter["scope"] = scope

    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": "incident_signature",
                "path": "signature.vec",
                "queryVector": vec,
                "numCandidates": 100,
                "limit": k,
                "filter": search_filter,
            }
        },
        {"$set": {"sim": {"$meta": "vectorSearchScore"}}},
    ]

    match_cond: dict[str, Any] = {"sim": {"$gte": min_similarity}}
    if current_id:
        match_cond["_id"] = {"$ne": current_id}
    pipeline.append({"$match": match_cond})

    pipeline.extend(
        [
            {
                "$lookup": {
                    "from": "actions",
                    "localField": "_id",
                    "foreignField": "incident_id",
                    "as": "acts",
                    "pipeline": [
                        {
                            "$match": {
                                "verification.verdict": {"$in": ["PASS", "FAIL"]},
                                "parent_action_id": None,
                            }
                        },
                        {
                            "$project": {
                                "type": 1,
                                "params": 1,
                                "verification.verdict": 1,
                                "ttr_s": 1,
                            }
                        },
                    ],
                }
            },
            {"$unwind": "$acts"},
            {
                "$group": {
                    "_id": "$acts.type",
                    "weight": {"$sum": "$sim"},
                    "tried": {"$sum": 1},
                    "passed": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$acts.verification.verdict", "PASS"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "w_pass": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$acts.verification.verdict", "PASS"]},
                                "$sim",
                                0,
                            ]
                        }
                    },
                    "ttr_med": {
                        "$median": {
                            "input": "$acts.ttr_s",
                            "method": "approximate",
                        }
                    },
                    "examples": {
                        "$topN": {
                            "n": 3,
                            "sortBy": {"sim": -1},
                            "output": {
                                "key": "$key",
                                "sim": "$sim",
                                "params": "$acts.params",
                            },
                        }
                    },
                }
            },
            {"$set": {"weighted_success": {"$divide": ["$w_pass", "$weight"]}}},
            {"$sort": {"weighted_success": -1, "ttr_med": 1}},
        ]
    )

    return pipeline
