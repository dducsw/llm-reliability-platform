"""A2 — Request rollup → sli_1m (Delivered ledger).

Collection: requests_ts
Kỹ thuật:   $dateTrunc, $percentile, histogram, $merge
Spec:       docs/30-data/aggregation-catalog.md#a2
"""

from __future__ import annotations

from typing import Any

from reflex_core.hist import BOUNDS_MS, NB

ID = "A2"
COLLECTION = "requests_ts"


def build(*, now: Any, from_: Any, to: Any, env: str = "local") -> list[dict[str, Any]]:
    bounds_list = list(BOUNDS_MS)
    return [
        {"$match": {"ts": {"$gte": from_, "$lt": to}}},
        {
            "$set": {
                "minute": {"$dateTrunc": {"date": "$ts", "unit": "minute"}},
                "ok": {"$in": ["$outcome", ["ok", "quality_fail"]]},
                "lb": {
                    "$cond": [
                        "$ok",
                        {
                            "$size": {
                                "$filter": {
                                    "input": bounds_list,
                                    "cond": {"$lte": ["$$this", "$latency_ms"]},
                                }
                            }
                        },
                        -1,
                    ]
                },
                "tb": {
                    "$cond": [
                        "$ok",
                        {
                            "$size": {
                                "$filter": {
                                    "input": bounds_list,
                                    "cond": {"$lte": ["$$this", "$ttft_ms"]},
                                }
                            }
                        },
                        -1,
                    ]
                },
            }
        },
        {
            "$group": {
                "_id": {"key": "$meta.route", "env": "$meta.env", "ts": "$minute"},
                "total": {"$sum": 1},
                "ok": {"$sum": {"$cond": ["$ok", 1, 0]}},
                "error": {"$sum": {"$cond": [{"$eq": ["$outcome", "error"]}, 1, 0]}},
                "timeout": {"$sum": {"$cond": [{"$eq": ["$outcome", "timeout"]}, 1, 0]}},
                "q_eligible": {"$sum": {"$cond": [{"$ne": [{"$type": "$quality"}, "missing"]}, 1, 0]}},
                "q_good": {"$sum": {"$cond": [{"$eq": ["$quality.pass", True]}, 1, 0]}},
                "pct": {
                    "$percentile": {
                        "input": "$latency_ms",
                        "p": [0.5, 0.95, 0.99],
                        "method": "approximate",
                    }
                },
                "ttft_pct": {
                    "$percentile": {
                        "input": "$ttft_ms",
                        "p": [0.95],
                        "method": "approximate",
                    }
                },
                "lbs": {"$push": "$lb"},
                "tbs": {"$push": "$tb"},
                "tokens_in": {"$sum": "$tokens_in"},
                "tokens_out": {"$sum": "$tokens_out"},
                "cost_usd": {"$sum": "$cost_usd"},
            }
        },
        {
            "$set": {
                "scope": "route",
                "key": "$_id.key",
                "env": "$_id.env",
                "ts": "$_id.ts",
                "err": {
                    "error": "$error",
                    "timeout": "$timeout",
                },
                "p50": {"$arrayElemAt": ["$pct", 0]},
                "p95": {"$arrayElemAt": ["$pct", 1]},
                "p99": {"$arrayElemAt": ["$pct", 2]},
                "ttft_p95": {"$arrayElemAt": ["$ttft_pct", 0]},
                "lat_hist": {
                    "$map": {
                        "input": {"$range": [0, NB]},
                        "as": "i",
                        "in": {
                            "$size": {
                                "$filter": {
                                    "input": "$lbs",
                                    "cond": {"$eq": ["$$this", "$$i"]},
                                }
                            }
                        },
                    }
                },
                "ttft_hist": {
                    "$map": {
                        "input": {"$range": [0, NB]},
                        "as": "i",
                        "in": {
                            "$size": {
                                "$filter": {
                                    "input": "$tbs",
                                    "cond": {"$eq": ["$$this", "$$i"]},
                                }
                            }
                        },
                    }
                },
                "watermark": now,
            }
        },
        {"$unset": ["_id", "pct", "ttft_pct", "lbs", "tbs", "error", "timeout"]},
        {
            "$merge": {
                "into": "sli_1m",
                "on": ["scope", "key", "env", "ts"],
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        },
    ]
