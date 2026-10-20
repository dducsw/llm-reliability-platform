"""A13 — Blast radius & chi phí của sự cố.

Collection: requests_ts
Kỹ thuật:   $group 2 tầng, $sum có điều kiện
Spec:       docs/30-data/aggregation-catalog.md#a13
"""

from __future__ import annotations

from typing import Any

ID = "A13"
COLLECTION = "requests_ts"


def build(*, route: Any, incident_id: Any, from_: Any, to: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
