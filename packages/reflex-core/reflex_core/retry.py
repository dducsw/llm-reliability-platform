"""Retry classification, backoff full-jitter, retry budget (token bucket) và rescue budget (cost)."""

from __future__ import annotations

from enum import StrEnum

from reflex_core.ids import Clock, Rng
from reflex_core.policy import RescueConfig, RetryConfig


class FailureClass(StrEnum):
    TRANSIENT = "transient"  # 5xx, timeout, connect, 429
    QUALITY = "quality"
    PERMANENT = "permanent"  # 400/401/403/404/422, context length


def classify(http_status: int | None, error_class: str | None, quality_failed: bool) -> FailureClass:
    raise NotImplementedError


def backoff_ms(attempt: int, rng: Rng, base_ms: int = 100, cap_ms: int = 2000) -> float:
    raise NotImplementedError


class RetryBudget:
    """Retry transient ≤ budget_ratio × request trong 10s gần nhất, mỗi route."""

    def __init__(self, config: RetryConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock

    def record_request(self) -> None:
        raise NotImplementedError

    def try_acquire(self) -> bool:
        raise NotImplementedError


class RescueBudget:
    """Quality retry giới hạn bằng chi phí (review F3), không dùng chung với RetryBudget."""

    def __init__(self, config: RescueConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock

    def record_cost(self, cost_usd: float) -> None:
        raise NotImplementedError

    def try_acquire(self, expected_cost_usd: float) -> bool:
        raise NotImplementedError
