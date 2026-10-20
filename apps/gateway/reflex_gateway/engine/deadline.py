"""Deadline propagation: chỉ bắn attempt mới khi remaining > p50(target)."""

from __future__ import annotations


class Deadline:
    def __init__(self, budget_ms: int) -> None:
        self._budget_ms = budget_ms

    def remaining_ms(self) -> float:
        raise NotImplementedError

    def allows(self, expected_ms: float) -> bool:
        raise NotImplementedError
