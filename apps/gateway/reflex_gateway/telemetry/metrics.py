"""DogStatsD emit cho request/attempt/quality/cost (tags theo reflex_telemetry.tags)."""

from __future__ import annotations

from datadog.dogstatsd import DogStatsd
from reflex_core.events import AttemptEvent, RequestEvent
from reflex_telemetry import tags as t

_statsd: DogStatsd | None = None


def configure(statsd: DogStatsd | None) -> None:
    global _statsd
    _statsd = statsd


def emit_request(event: RequestEvent) -> None:
    if _statsd is None:
        return
    tags = [
        *t.base_tags(event.meta.env, route=event.meta.route, target=event.final_target),
        f"{t.OUTCOME}:{event.outcome.value}",
        f"{t.POLICY_VERSION}:{event.policy_version}",
    ]
    _statsd.increment(t.M_REQUEST, tags=tags)
    _statsd.distribution(t.M_REQUEST_LATENCY, event.latency_ms, tags=tags)
    _statsd.distribution(t.M_COST_USD, event.cost_usd, tags=tags)
    if event.quality is not None:
        _statsd.increment(t.M_QUALITY_TOTAL, tags=tags)
        if event.quality.pass_:
            _statsd.increment(t.M_QUALITY_PASS, tags=tags)
    if event.attempts:
        _statsd.gauge(t.M_RETRY_AMPLIFICATION, float(event.attempts), tags=tags)


def emit_attempt(event: AttemptEvent) -> None:
    if _statsd is None:
        return
    tags = [
        f"{t.ENV}:{event.meta.env}",
        f"{t.ROUTE}:{event.route}",
        f"{t.TARGET}:{event.meta.target}",
        f"{t.ATTEMPT_KIND}:{event.kind.value}",
        f"{t.OUTCOME}:{event.outcome.value}",
        f"{t.GATEWAY_ID}:{event.gateway_id}",
    ]
    _statsd.increment(t.M_ATTEMPT, tags=tags)
    if event.quality is not None:
        _statsd.increment(t.M_ATTEMPT_QUALITY_TOTAL, tags=tags)
        if event.quality.pass_:
            _statsd.increment(t.M_ATTEMPT_QUALITY_PASS, tags=tags)
    _statsd.distribution(t.M_ATTEMPT_LATENCY, event.latency_ms, tags=tags)
    if event.ttft_ms is not None:
        _statsd.distribution(t.M_ATTEMPT_TTFT, event.ttft_ms, tags=tags)
