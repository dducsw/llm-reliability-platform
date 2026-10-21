"""A14 — Baseline hour-of-week từ dataset public.

Collection: bench_ts → baselines
Kỹ thuật:   $dateToParts, $median, $merge
Spec:       docs/30-data/aggregation-catalog.md#a14
"""

from __future__ import annotations

from typing import Any

ID = "A14"
COLLECTION = "bench_ts"


def build() -> list[dict[str, Any]]:
    raise NotImplementedError
