from datetime import datetime, timedelta

from reflex_core.policy import RescueConfig, RetryConfig
from reflex_core.retry import (
    FailureClass,
    RescueBudget,
    RetryBudget,
    backoff_ms,
    classify,
)


class MockClock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 10, 21, 12, 0, 0)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class MockRng:
    def random(self) -> float:
        return 0.5

    def uniform(self, a: float, b: float) -> float:
        return (a + b) / 2.0


def test_classify_errors() -> None:
    assert classify(200, None, quality_failed=True) == FailureClass.QUALITY
    assert classify(400, "invalid_request_error", quality_failed=False) == FailureClass.PERMANENT
    assert classify(503, "server_error", quality_failed=False) == FailureClass.TRANSIENT
    assert classify(429, "rate_limited", quality_failed=False) == FailureClass.TRANSIENT


def test_backoff_ms() -> None:
    rng = MockRng()
    delay_0 = backoff_ms(0, rng, base_ms=100, cap_ms=2000)
    delay_1 = backoff_ms(1, rng, base_ms=100, cap_ms=2000)
    assert delay_0 == 50.0
    assert delay_1 == 100.0


def test_retry_budget_enforcement() -> None:
    clock = MockClock()
    config = RetryConfig(budget_ratio=0.2)
    budget = RetryBudget(config, clock)

    # 10 requests -> 2 retry tokens
    for _ in range(10):
        budget.record_request()

    assert budget.try_acquire() is True
    assert budget.try_acquire() is True
    assert budget.try_acquire() is False  # Đã dùng hết 2 lượt retry


def test_rescue_budget_cost_limit() -> None:
    clock = MockClock()
    config = RescueConfig(enabled=True, max_extra_cost_ratio=0.5)
    rescue = RescueBudget(config, clock)

    # Chi phí base 1.0 USD -> trần rescue là 0.5 USD
    rescue.record_cost(1.0)

    assert rescue.try_acquire(0.2) is True
    assert rescue.try_acquire(0.2) is True
    assert rescue.try_acquire(0.2) is False  # 0.2 + 0.2 + 0.2 = 0.6 > 0.5 -> Bị chặn
