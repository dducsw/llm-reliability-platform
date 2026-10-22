"""Deadline propagation: chỉ bắn attempt mới khi remaining > p50(target)."""

from __future__ import annotations

import time
from collections.abc import Callable


class Deadline:
    def __init__(self, budget_ms: int, now: Callable[[], float] = time.monotonic) -> None:
        self._budget_ms = budget_ms
        self._now = now
        self._started = now()

    def remaining_ms(self) -> float:
        elapsed_ms = (self._now() - self._started) * 1000.0
        return max(0.0, self._budget_ms - elapsed_ms)

    def allows(self, expected_ms: float) -> bool:
        return self.remaining_ms() > expected_ms
