"""Bounded in-memory queue. Đầy thì drop + đếm reflex.telemetry.dropped (không chặn request)."""

from __future__ import annotations

import asyncio
from reflex_core.events import AttemptEvent, RequestEvent


class TelemetryQueue:
    def __init__(self, maxsize: int = 10_000) -> None:
        self._maxsize = maxsize
        self._queue: asyncio.Queue[RequestEvent | AttemptEvent] = asyncio.Queue(maxsize=maxsize)
        self.dropped: int = 0

    def put_nowait(self, event: RequestEvent | AttemptEvent) -> bool:
        try:
            self._queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            self.dropped += 1
            return False

    async def get(self) -> RequestEvent | AttemptEvent:
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()
