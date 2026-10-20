"""Sliding-window circuit breaker: closed → open → half_open → closed.

Bất biến: không bao giờ closed → half_open trực tiếp; open không vượt open_max_s.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from reflex_core.ids import Clock
from reflex_core.policy import BreakerConfig


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, config: BreakerConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock

    @property
    def state(self) -> BreakerState:
        raise NotImplementedError

    def allow(self) -> bool:
        raise NotImplementedError

    def record(self, success: bool, at: datetime | None = None) -> None:
        raise NotImplementedError

    def force_open(self, duration_s: int) -> None:
        """Dùng cho action `open_circuit_global`."""
        raise NotImplementedError
