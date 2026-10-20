"""Bounded in-memory queue. Đầy thì drop + đếm reflex.telemetry.dropped (không chặn request)."""

from __future__ import annotations

from reflex_core.events import AttemptEvent, RequestEvent


class TelemetryQueue:
    def __init__(self, maxsize: int) -> None:
        self._maxsize = maxsize

    def put_nowait(self, event: RequestEvent | AttemptEvent) -> bool:
        raise NotImplementedError
