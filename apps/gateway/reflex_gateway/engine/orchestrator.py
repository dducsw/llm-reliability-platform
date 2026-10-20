"""Attempt loop: router.decide → adapter.call → validators → retry/rescue/hedge → events."""

from __future__ import annotations

from dataclasses import dataclass

from reflex_core.events import AttemptEvent, RequestEvent


@dataclass(slots=True)
class RequestContext:
    request_id: str
    route: str
    priority: int
    session: str | None
    deadline_ms: int
    trace_id: str | None = None


@dataclass(slots=True)
class OrchestratorResult:
    body: dict
    request_event: RequestEvent
    attempt_events: list[AttemptEvent]


class Orchestrator:
    async def complete(self, ctx: RequestContext, payload: dict) -> OrchestratorResult:
        raise NotImplementedError

    async def stream(self, ctx: RequestContext, payload: dict):  # type: ignore[no-untyped-def]
        """Async iterator SSE chunks; validate khi stream kết thúc."""
        raise NotImplementedError
