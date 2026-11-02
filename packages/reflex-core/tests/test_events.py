"""Unit tests cho reflex_core.events và reflex_core.signature — xem docs/70-delivery/testing-strategy.md."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from reflex_core import signature
from reflex_core.events import (
    AttemptEvent,
    AttemptKind,
    AttemptOutcome,
    QualityResult,
    RequestEvent,
    RequestOutcome,
)

TS = datetime(2026, 11, 1, tzinfo=UTC)


def _request(**over: object) -> RequestEvent:
    base: dict[str, object] = {
        "ts": TS,
        "meta": {"route": "order.extract", "env": "local"},
        "request_id": "r1",
        "outcome": "ok",
        "latency_ms": 120.0,
        "policy_version": 3,
    }
    return RequestEvent.model_validate({**base, **over})


def test_request_event_defaults_and_enum() -> None:
    ev = _request()
    assert ev.outcome is RequestOutcome.OK
    assert ev.v == 1 and ev.attempts == 1 and not ev.hedged
    assert ev.meta.synthetic is False


def test_events_forbid_unknown_fields_and_are_frozen() -> None:
    with pytest.raises(ValidationError):
        _request(unknown_field=1)
    ev = _request()
    with pytest.raises(ValidationError):
        ev.latency_ms = 1.0  # type: ignore[misc]


def test_invalid_outcome_rejected() -> None:
    with pytest.raises(ValidationError):
        _request(outcome="exploded")


def test_quality_alias_round_trips_as_pass() -> None:
    q = QualityResult.model_validate({"pass": False, "failed": ["json_schema"]})
    assert q.pass_ is False
    assert q.model_dump(by_alias=True)["pass"] is False


def test_attempt_event_parses_kind_and_outcome() -> None:
    ev = AttemptEvent.model_validate(
        {
            "ts": TS,
            "meta": {"target": "vendorA:large", "env": "local"},
            "request_id": "r1",
            "route": "order.extract",
            "attempt_no": 2,
            "kind": "hedge",
            "outcome": "rate_limited",
            "latency_ms": 900.0,
            "gateway_id": "gw-1",
            "breaker_state": "closed",
        }
    )
    assert ev.kind is AttemptKind.HEDGE
    assert ev.outcome is AttemptOutcome.RATE_LIMITED


def test_signature_layout_matches_a9_channel_major() -> None:
    series = {ch: [float(i)] * signature.STEPS for i, ch in enumerate(signature.CHANNELS)}
    vec = signature.build(series)
    assert len(vec) == signature.DIM == 64
    assert vec[0] == 0.0 and vec[16] == 1.0 and vec[32] == 2.0 and vec[63] == 3.0


def test_signature_missing_channel_is_zero_and_wrong_length_raises() -> None:
    vec = signature.build({"err_ratio": [0.5] * 16})
    assert vec[:16] == [0.5] * 16 and set(vec[16:]) == {0.0}
    with pytest.raises(ValueError):
        signature.build({"err_ratio": [0.5] * 15})


def test_cosine() -> None:
    a = signature.build({"err_ratio": [1.0] * 16})
    b = signature.build({"quality_fail_ratio": [1.0] * 16})
    assert signature.cosine(a, a) == pytest.approx(1.0)
    assert signature.cosine(a, b) == pytest.approx(0.0)
    assert signature.cosine(a, [0.0] * 64) == 0.0
    with pytest.raises(ValueError):
        signature.cosine(a, [1.0])
