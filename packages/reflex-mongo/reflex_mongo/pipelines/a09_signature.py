"""A9 — Incident signature vector 64 chiều.

Collection: sli_1m
Kỹ thuật:   $densify, $fill linear, chuẩn hóa, $concatArrays
Spec:       docs/30-data/aggregation-catalog.md#a9
"""

from __future__ import annotations

from typing import Any

ID = "A9"
COLLECTION = "sli_1m"


def build(*, scope: Any, key: Any, detected_at: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
