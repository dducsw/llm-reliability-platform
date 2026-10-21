"""A16 — Recovery Proof data (trước/sau).

Collection: sli_1m
Kỹ thuật:   $facet trước/sau
Spec:       docs/30-data/aggregation-catalog.md#a16
"""

from __future__ import annotations

from typing import Any

ID = "A16"
COLLECTION = "sli_1m"


def build(*, scope: Any, key: Any, baseline: Any, after: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
