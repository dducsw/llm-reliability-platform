"""A3 — Hourly rollup có cộng histogram.

Collection: sli_1m → sli_1h
Kỹ thuật:   $reduce + $map cộng vector histogram
Spec:       docs/30-data/aggregation-catalog.md#a3
"""

from __future__ import annotations

from typing import Any

from reflex_core.hist import NB

ID = "A3"
COLLECTION = "sli_1m"


def build(*, from_: Any, to: Any) -> list[dict[str, Any]]:
    zeros_nb = [0] * NB
    return [
        {"$match": {"ts": {"$gte": from_, "$lt": to}}},
        {
            "$group": {
                "_id": {
                    "scope": "$scope",
                    "key": "$key",
                    "env": "$env",
                    "ts": {"$dateTrunc": {"date": "$ts", "unit": "hour"}},
                },
                "total": {"$sum": "$total"},
                "ok": {"$sum": "$ok"},
                "q_eligible": {"$sum": "$q_eligible"},
                "q_good": {"$sum": "$q_good"},
                "cost_usd": {"$sum": "$cost_usd"},
                "tokens_in": {"$sum": "$tokens_in"},
                "tokens_out": {"$sum": "$tokens_out"},
                "lh": {"$push": "$lat_hist"},
                "th": {"$push": "$ttft_hist"},
            }
        },
        {
            "$set": {
                "lat_hist": {
                    "$reduce": {
                        "input": "$lh",
                        "initialValue": zeros_nb,
                        "in": {
                            "$map": {
                                "input": {"$range": [0, NB]},
                                "as": "i",
                                "in": {
                                    "$add": [
                                        {"$arrayElemAt": ["$$value", "$$i"]},
                                        {"$arrayElemAt": ["$$this", "$$i"]},
                                    ]
                                },
                            }
                        },
                    }
                },
                "ttft_hist": {
                    "$reduce": {
                        "input": "$th",
                        "initialValue": zeros_nb,
                        "in": {
                            "$map": {
                                "input": {"$range": [0, NB]},
                                "as": "i",
                                "in": {
                                    "$add": [
                                        {"$arrayElemAt": ["$$value", "$$i"]},
                                        {"$arrayElemAt": ["$$this", "$$i"]},
                                    ]
                                },
                            }
                        },
                    }
                },
            }
        },
        {
            "$set": {
                "scope": "$_id.scope",
                "key": "$_id.key",
                "env": "$_id.env",
                "ts": "$_id.ts",
            }
        },
        {"$unset": ["_id", "lh", "th"]},
        {
            "$merge": {
                "into": "sli_1h",
                "on": ["scope", "key", "env", "ts"],
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        },
    ]
