"""DogStatsD emit cho request/attempt/quality/cost (tags theo reflex_telemetry.tags)."""

from __future__ import annotations

from reflex_core.events import AttemptEvent, RequestEvent


def emit_request(event: RequestEvent) -> None:
    raise NotImplementedError


def emit_attempt(event: AttemptEvent) -> None:
    raise NotImplementedError
