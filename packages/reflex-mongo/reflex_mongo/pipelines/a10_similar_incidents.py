"""A10 — Sự cố tương tự + hiệu quả action.

Collection: incidents ⨝ actions
Kỹ thuật:   $vectorSearch, $lookup, $median
Spec:       docs/30-data/aggregation-catalog.md#a10
"""

from __future__ import annotations

from typing import Any

ID = "A10"
COLLECTION = "incidents"


def build(*, vec: Any, sli: Any, scope: Any, k: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
