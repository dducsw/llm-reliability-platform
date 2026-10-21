"""A4 — Multi-window burn rate trong một lần quét.

Collection: sli_1m
Kỹ thuật:   conditional $sum
Spec:       docs/30-data/aggregation-catalog.md#a4
"""

from __future__ import annotations

from typing import Any

ID = "A4"
COLLECTION = "sli_1m"


def build(*, now: Any, slos: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
