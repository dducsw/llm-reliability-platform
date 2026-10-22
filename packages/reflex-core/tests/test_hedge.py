from datetime import datetime, timedelta

from reflex_core.hedge import HedgeBudget, should_shed
from reflex_core.policy import HedgeConfig, ShedConfig


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 21, 12, 0, 0)

    def __call__(self) -> datetime:
        return self.now


def test_hedge_budget_disabled_never_acquires() -> None:
    b = HedgeBudget(HedgeConfig(enabled=False), _Clock())
    b.record_request()
    assert b.try_acquire() is False


def test_hedge_budget_caps_extra_attempts_by_ratio() -> None:
    b = HedgeBudget(HedgeConfig(enabled=True, max_extra_cost_ratio=0.1), _Clock())
    for _ in range(30):
        b.record_request()
    assert [b.try_acquire() for _ in range(4)] == [True, True, True, False]


def test_hedge_budget_needs_traffic_first() -> None:
    b = HedgeBudget(HedgeConfig(enabled=True, max_extra_cost_ratio=0.1), _Clock())
    assert b.try_acquire() is False


def test_hedge_budget_window_slides() -> None:
    clock = _Clock()
    b = HedgeBudget(HedgeConfig(enabled=True, max_extra_cost_ratio=0.5), clock)
    for _ in range(4):
        b.record_request()
    assert b.try_acquire() and b.try_acquire() and not b.try_acquire()
    clock.now += timedelta(seconds=301)
    for _ in range(4):
        b.record_request()
    assert b.try_acquire() is True


def test_should_shed_only_when_degraded_and_low_priority() -> None:
    cfg = ShedConfig(when_all_degraded_min_priority=2)
    assert should_shed(cfg, priority=2, all_degraded=True) is True
    assert should_shed(cfg, priority=1, all_degraded=True) is False
    assert should_shed(cfg, priority=2, all_degraded=False) is False
