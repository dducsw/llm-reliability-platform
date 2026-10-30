"""Chất lượng theo attempt phải gắn target đã gọi (M3 Provider quality, không bị rescue che)."""

from datetime import UTC, datetime
from typing import Any

from reflex_core.events import (
    AttemptEvent,
    AttemptKind,
    AttemptMeta,
    AttemptOutcome,
    QualityResult,
)
from reflex_gateway.telemetry import metrics


class _Statsd:
    def __init__(self) -> None:
        self.incs: list[tuple[str, list[str] | None]] = []

    def increment(self, name: str, tags: list[str] | None = None) -> None:
        self.incs.append((name, tags))

    def distribution(self, *_a: Any, **_k: Any) -> None:
        pass


def _attempt(passed: bool | None) -> AttemptEvent:
    quality = None if passed is None else QualityResult(pass_=passed)
    return AttemptEvent(
        ts=datetime(2026, 10, 28, tzinfo=UTC),
        meta=AttemptMeta(target="vendorA:large", env="local"),
        request_id="r1",
        route="order.extract",
        attempt_no=1,
        kind=AttemptKind.PRIMARY,
        outcome=AttemptOutcome.OK,
        latency_ms=10.0,
        quality=quality,
        gateway_id="gw-1",
        breaker_state="closed",
    )


def _emitted(passed: bool | None) -> list[tuple[str, list[str]]]:
    fake = _Statsd()
    metrics.configure(fake)  # type: ignore[arg-type]
    try:
        metrics.emit_attempt(_attempt(passed))
    finally:
        metrics.configure(None)
    return fake.incs


def test_failed_quality_counts_total_only() -> None:
    names = [n for n, _ in _emitted(False)]
    assert "reflex.attempt.quality.total" in names
    assert "reflex.attempt.quality.pass" not in names


def test_passed_quality_counts_total_and_pass_with_target_tag() -> None:
    by_name = {n: t or [] for n, t in _emitted(True)}
    assert "reflex.attempt.quality.pass" in by_name
    assert "target:vendorA:large" in by_name["reflex.attempt.quality.total"]


def test_attempt_without_quality_check_emits_no_quality_metric() -> None:
    assert not [n for n, _ in _emitted(None) if "quality" in n]


def test_full_queue_emits_telemetry_dropped() -> None:
    from reflex_gateway.telemetry.queue import TelemetryQueue

    fake = _Statsd()
    metrics.configure(fake)  # type: ignore[arg-type]
    try:
        q = TelemetryQueue(maxsize=1)
        assert q.put_nowait(_attempt(True)) is True
        assert q.put_nowait(_attempt(True)) is False  # đầy → drop
    finally:
        metrics.configure(None)
    assert fake.incs == [("reflex.telemetry.dropped", None)]


def _request(latency_ms: float, outcome: str = "ok") -> Any:
    from reflex_core.events import RequestEvent, RequestMeta, RequestOutcome

    return RequestEvent(
        ts=datetime(2026, 10, 28, tzinfo=UTC),
        meta=RequestMeta(env="local", route="chat.reply"),
        request_id="r1",
        outcome=RequestOutcome(outcome),
        final_target="vendorA:large",
        latency_ms=latency_ms,
        policy_version=1,
    )


def _under(latency_ms: float, outcome: str = "ok") -> list[list[str]]:
    class _S(_Statsd):
        def gauge(self, *_a: Any, **_k: Any) -> None:
            pass

    fake = _S()
    metrics.configure(fake)  # type: ignore[arg-type]
    try:
        metrics.emit_request(_request(latency_ms, outcome))
    finally:
        metrics.configure(None)
    return [tags or [] for n, tags in fake.incs if n == "reflex.request.under_threshold"]


def test_fast_ok_request_counts_under_threshold() -> None:
    emitted = _under(1500.0)
    assert len(emitted) == 1 and "threshold:2000" in emitted[0]


def test_slow_or_failed_request_not_under_threshold() -> None:
    assert _under(2500.0) == []
    assert _under(100.0, "error") == []
