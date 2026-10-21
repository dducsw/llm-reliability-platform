"""A12 — Top-k contributors theo chiều.

Collection: attempts_ts
Kỹ thuật:   $facet đa chiều
Spec:       docs/30-data/aggregation-catalog.md#a12
"""

from __future__ import annotations

from typing import Any

ID = "A12"
COLLECTION = "attempts_ts"


def build(*, target: Any, from_: Any, to: Any, k: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
