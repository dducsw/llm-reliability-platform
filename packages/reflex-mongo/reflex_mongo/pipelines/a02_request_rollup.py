"""A2 — Request rollup → sli_1m (Delivered ledger).

Collection: requests_ts
Kỹ thuật:   như A1
Spec:       docs/30-data/aggregation-catalog.md#a2
"""

from __future__ import annotations

from typing import Any

ID = "A2"
COLLECTION = "requests_ts"


def build(*, now: Any, from_: Any, to: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
