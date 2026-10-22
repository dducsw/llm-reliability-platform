"""Retry classification, backoff full-jitter, retry budget (token bucket) và rescue budget (cost)."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from enum import StrEnum

from reflex_core.ids import Clock, Rng
from reflex_core.policy import RescueConfig, RetryConfig


class FailureClass(StrEnum):
    TRANSIENT = "transient"  # 5xx, timeout, connect, 429
    QUALITY = "quality"
    PERMANENT = "permanent"  # 400/401/403/404/422, context length


def classify(
    http_status: int | None,
    error_class: str | None,
    quality_failed: bool,
) -> FailureClass:
    if quality_failed:
        return FailureClass.QUALITY

    if http_status in (400, 401, 403, 404, 422) or error_class in (
        "context_length_exceeded",
        "invalid_request_error",
        "authentication_error",
    ):
        return FailureClass.PERMANENT

    if (http_status is not None and (http_status == 429 or http_status >= 500)) or error_class in (
        "timeout",
        "connect_error",
        "rate_limited",
        "server_error",
    ):
        return FailureClass.TRANSIENT

    return (
        FailureClass.PERMANENT
        if http_status and 400 <= http_status < 500
        else FailureClass.TRANSIENT
    )


def backoff_ms(attempt: int, rng: Rng, base_ms: int = 100, cap_ms: int = 2000) -> float:
    exp_delay = base_ms * (2**attempt)
    ceiling = min(float(cap_ms), float(exp_delay))
    return rng.uniform(0.0, ceiling)


class RetryBudget:
    """Retry transient ≤ budget_ratio × request trong 10s gần nhất, mỗi route."""

    def __init__(self, config: RetryConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock
        self._requests: deque[datetime] = deque()
        self._retries: deque[datetime] = deque()

    def record_request(self) -> None:
        now = self._clock()
        self._requests.append(now)
        self._prune(now)

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=10)
        while self._requests and self._requests[0] < cutoff:
            self._requests.popleft()
        while self._retries and self._retries[0] < cutoff:
            self._retries.popleft()

    def try_acquire(self) -> bool:
        now = self._clock()
        self._prune(now)

        n_req = len(self._requests)
        allowed_retries = max(1, int(n_req * self._config.budget_ratio))
        if len(self._retries) < allowed_retries:
            self._retries.append(now)
            return True
        return False


class RescueBudget:
    """Quality retry giới hạn bằng chi phí (review F3), không dùng chung với RetryBudget."""

    def __init__(self, config: RescueConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock
        self._base_costs: deque[tuple[datetime, float]] = deque()
        self._rescue_costs: deque[tuple[datetime, float]] = deque()

    def record_cost(self, cost_usd: float) -> None:
        now = self._clock()
        self._base_costs.append((now, cost_usd))
        self._prune(now)

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=300)  # Cửa sổ 5 phút
        while self._base_costs and self._base_costs[0][0] < cutoff:
            self._base_costs.popleft()
        while self._rescue_costs and self._rescue_costs[0][0] < cutoff:
            self._rescue_costs.popleft()

    def try_acquire(self, expected_cost_usd: float) -> bool:
        if not self._config.enabled:
            return False

        now = self._clock()
        self._prune(now)

        total_base = sum(c for _, c in self._base_costs)
        total_rescue = sum(c for _, c in self._rescue_costs)

        # Giới hạn trần chi phí bổ sung theo tỷ lệ
        max_rescue = max(0.01, total_base * self._config.max_extra_cost_ratio)
        if total_rescue + expected_cost_usd <= max_rescue:
            self._rescue_costs.append((now, expected_cost_usd))
            return True
        return False
