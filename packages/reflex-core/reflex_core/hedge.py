"""Hedging: bắn attempt song song khi primary vượt p95 TTFT, giới hạn bằng chi phí."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

from reflex_core.ids import Clock
from reflex_core.policy import HedgeConfig, ShedConfig


def hedge_delay_ms(config: HedgeConfig, ttft_p95_ms: float | None) -> float | None:
    if not config.enabled:
        return None
    if ttft_p95_ms is None or ttft_p95_ms <= 0:
        return None
    return float(ttft_p95_ms)


def should_hedge(config: HedgeConfig, spent_ratio: float) -> bool:
    if not config.enabled:
        return False
    return spent_ratio <= config.max_extra_cost_ratio


class HedgeBudget:
    """Số hedge ≤ max_extra_cost_ratio × số request của route trong cửa sổ trượt 5 phút.

    Mỗi hedge là một attempt thừa nên đếm theo attempt là proxy đủ tốt cho chi phí thừa.
    """

    WINDOW_S = 300

    def __init__(self, config: HedgeConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock
        self._requests: deque[datetime] = deque()
        self._hedges: deque[datetime] = deque()

    def configure(self, config: HedgeConfig) -> None:
        """Policy hot-reload đổi ngưỡng mà không mất cửa sổ đếm."""
        self._config = config

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.WINDOW_S)
        for q in (self._requests, self._hedges):
            while q and q[0] < cutoff:
                q.popleft()

    def record_request(self) -> None:
        now = self._clock()
        self._requests.append(now)
        self._prune(now)

    def try_acquire(self) -> bool:
        if not self._config.enabled:
            return False
        now = self._clock()
        self._prune(now)
        if (len(self._hedges) + 1) > len(self._requests) * self._config.max_extra_cost_ratio:
            return False
        self._hedges.append(now)
        return True


def should_shed(config: ShedConfig, priority: int, all_degraded: bool) -> bool:
    """P0 quan trọng nhất; priority >= ngưỡng bị shed khi mọi candidate đều degraded."""
    return all_degraded and priority >= config.when_all_degraded_min_priority
