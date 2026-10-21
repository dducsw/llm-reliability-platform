"""A1 — Attempt rollup → sli_1m (Provider ledger).

Collection: attempts_ts
Kỹ thuật:   $dateTrunc, $percentile, histogram, $merge on nhiều field
Spec:       docs/30-data/aggregation-catalog.md#a1
"""

from __future__ import annotations

from typing import Any

ID = "A1"
COLLECTION = "attempts_ts"


def build(*, now: Any, from_: Any, to: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
