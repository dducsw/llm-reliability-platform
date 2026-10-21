"""A3 — Hourly rollup có cộng histogram sli_1m → sli_1h.

Collection: sli_1m
Kỹ thuật:   $reduce + $map cộng vector
Spec:       docs/30-data/aggregation-catalog.md#a3
"""

from __future__ import annotations

from typing import Any

ID = "A3"
COLLECTION = "sli_1m"


def build(*, from_: Any, to: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
