"""A8 — First-bad-at (cho MTTD).

Collection: sli_1m
Kỹ thuật:   $setWindowFields ($shift)
Spec:       docs/30-data/aggregation-catalog.md#a8
"""

from __future__ import annotations

from typing import Any

ID = "A8"
COLLECTION = "sli_1m"


def build(*, scope: Any, key: Any, detected_at: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
