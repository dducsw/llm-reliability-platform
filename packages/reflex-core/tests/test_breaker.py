from datetime import datetime, timedelta

import pytest
from reflex_core.breaker import BreakerState, CircuitBreaker
from reflex_core.policy import BreakerConfig


class MockClock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 10, 21, 12, 0, 0)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def test_breaker_trip_to_open_and_recover() -> None:
    clock = MockClock()
    config = BreakerConfig(
        window_s=20,
        min_requests=4,
        open_error_ratio=0.5,
        open_base_s=10,
        open_max_s=60,
        half_open_probes=2,
    )
    cb = CircuitBreaker(config, clock)

    assert cb.state == BreakerState.CLOSED
    assert cb.allow() is True

    # Ghi nhận 2 success, 2 error -> 50% error trên 4 requests -> Trip to Open!
    cb.record(True)
    cb.record(True)
    cb.record(False)
    assert cb.state == BreakerState.CLOSED

    cb.record(False)
    assert cb.state == BreakerState.OPEN
    assert cb.allow() is False

    # Chưa hết 10s -> vẫn Open
    clock.advance(5)
    assert cb.state == BreakerState.OPEN
    assert cb.allow() is False

    # Hết 10s -> HalfOpen
    clock.advance(6)
    assert cb.state == BreakerState.HALF_OPEN
    assert cb.allow() is True

    # Probe 1 thành công
    cb.record(True)
    assert cb.state == BreakerState.HALF_OPEN

    # Probe 2 thành công -> Hồi phục về Closed
    assert cb.allow() is True
    cb.record(True)
    assert cb.state == BreakerState.CLOSED
    assert cb.allow() is True


def test_breaker_half_open_failure_re_trips() -> None:
    clock = MockClock()
    config = BreakerConfig(
        window_s=20,
        min_requests=2,
        open_error_ratio=0.5,
        open_base_s=5,
        half_open_probes=2,
    )
    cb = CircuitBreaker(config, clock)

    cb.record(False)
    cb.record(False)
    assert cb.state == BreakerState.OPEN

    # Hết 5s -> HalfOpen
    clock.advance(6)
    assert cb.state == BreakerState.HALF_OPEN

    # Probe thất bại -> Lập tức quay lại Open với backoff tăng
    cb.record(False)
    assert cb.state == BreakerState.OPEN
