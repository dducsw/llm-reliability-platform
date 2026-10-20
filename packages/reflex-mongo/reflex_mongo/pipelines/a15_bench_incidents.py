"""A15 — Khai thác sự cố thật trong dataset.

Collection: bench_ts
Kỹ thuật:   $setWindowFields range window
Spec:       docs/30-data/aggregation-catalog.md#a15
"""

from __future__ import annotations

from typing import Any

ID = "A15"
COLLECTION = "bench_ts"


def build(*, model: Any, from_: Any, to: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
