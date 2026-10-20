"""A17 — MTTD / MTTA / MTTR theo SLI & side.

Collection: incidents
Kỹ thuật:   $percentile trên thời lượng
Spec:       docs/30-data/aggregation-catalog.md#a17
"""

from __future__ import annotations

from typing import Any

ID = "A17"
COLLECTION = "incidents"


def build(*, from_: Any, to: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
