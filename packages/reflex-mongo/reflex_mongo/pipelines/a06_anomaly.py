"""A6 — Anomaly z-score + EWMA.

Collection: sli_1m
Kỹ thuật:   $setWindowFields, $stdDevSamp, $expMovingAvg
Spec:       docs/30-data/aggregation-catalog.md#a6
"""

from __future__ import annotations

from typing import Any

ID = "A6"
COLLECTION = "sli_1m"


def build(*, now: Any, scope: Any, key: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
