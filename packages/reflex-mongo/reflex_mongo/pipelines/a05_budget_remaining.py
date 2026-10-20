"""A5 — Error budget còn lại.

Collection: sli_1h ∪ sli_1m
Kỹ thuật:   $unionWith
Spec:       docs/30-data/aggregation-catalog.md#a5
"""

from __future__ import annotations

from typing import Any

ID = "A5"
COLLECTION = "sli_1h"


def build(*, now: Any, slo: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
