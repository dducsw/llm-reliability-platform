"""A18 — Cost-of-reliability theo ngày (VN tz).

Collection: sli_1h
Kỹ thuật:   $dateTrunc + timezone Asia/Ho_Chi_Minh
Spec:       docs/30-data/aggregation-catalog.md#a18
"""

from __future__ import annotations

from typing import Any

ID = "A18"
COLLECTION = "sli_1h"


def build(*, from_: Any, to: Any) -> list[dict[str, Any]]:
    raise NotImplementedError
