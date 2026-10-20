"""A7 — Probe blindness (mất tín hiệu).

Collection: probes_ts
Kỹ thuật:   $densify, $fill
Spec:       docs/30-data/aggregation-catalog.md#a7
"""

from __future__ import annotations

from typing import Any

ID = "A7"
COLLECTION = "probes_ts"


def build(*, now: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
