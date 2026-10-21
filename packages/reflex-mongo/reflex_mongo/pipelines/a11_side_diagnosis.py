"""A11 — Chẩn đoán phân biệt: provider hay gateway.

Collection: probes_ts
Kỹ thuật:   $group theo meta.path
Spec:       docs/30-data/aggregation-catalog.md#a11
"""

from __future__ import annotations

from typing import Any

ID = "A11"
COLLECTION = "probes_ts"


def build(*, target: Any, from_: Any, to: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
