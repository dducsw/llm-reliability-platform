"""Sliding-window circuit breaker: closed → open → half_open → closed.

Bất biến: không bao giờ closed → half_open trực tiếp; open không vượt open_max_s.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
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
        self._state = BreakerState.CLOSED
        self._window: deque[tuple[datetime, bool]] = deque()
        self._opened_at: datetime | None = None
        self._open_duration_s: float = float(config.open_base_s)
        self._failure_count: int = 0
        self._probes_sent: int = 0
        self._probe_successes: int = 0

    @property
    def state(self) -> BreakerState:
        self._check_half_open()
        return self._state

    def _check_half_open(self) -> None:
        if self._state == BreakerState.OPEN and self._opened_at is not None:
            now = self._clock()
            if now >= self._opened_at + timedelta(seconds=self._open_duration_s):
                self._state = BreakerState.HALF_OPEN
                self._probes_sent = 0
                self._probe_successes = 0

    def allow(self) -> bool:
        self._check_half_open()
        if self._state == BreakerState.CLOSED:
            return True
        if self._state == BreakerState.HALF_OPEN:
            if self._probes_sent < self._config.half_open_probes:
                self._probes_sent += 1
                return True
            return False
        return False

    def record(self, success: bool, at: datetime | None = None) -> None:
        now = at or self._clock()
        self._check_half_open()

        if self._state == BreakerState.CLOSED:
            self._window.append((now, success))
            # Cắt tỉa window
            cutoff = now - timedelta(seconds=self._config.window_s)
            while self._window and self._window[0][0] < cutoff:
                self._window.popleft()

            n = len(self._window)
            if n >= self._config.min_requests:
                errors = sum(1 for _, ok in self._window if not ok)
                ratio = errors / n
                if ratio >= self._config.open_error_ratio:
                    self._trip(now)

        elif self._state == BreakerState.HALF_OPEN:
            if not success:
                self._trip(now)
            else:
                self._probe_successes += 1
                if self._probe_successes >= self._config.half_open_probes:
                    # Hồi phục hoàn toàn về closed
                    self._state = BreakerState.CLOSED
                    self._failure_count = 0
                    self._window.clear()

    def _trip(self, now: datetime) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = now
        duration = self._config.open_base_s * (2**self._failure_count)
        self._open_duration_s = min(float(self._config.open_max_s), float(duration))
        self._failure_count += 1
        self._window.clear()

    def force_open(self, duration_s: int) -> None:
        """Dùng cho action `open_circuit_global`."""
        self._state = BreakerState.OPEN
        self._opened_at = self._clock()
        self._open_duration_s = float(duration_s)
        self._window.clear()
