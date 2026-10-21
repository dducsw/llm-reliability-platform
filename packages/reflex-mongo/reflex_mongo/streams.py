"""Change Stream consumer với checkpoint/resume token (stream_checkpoints).

Chỉ watch collection thường (policies, health_state, incidents, actions, chaos_runs) —
Time Series không hỗ trợ Change Streams (ADR-0005).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class StreamConsumer:
    def __init__(
        self,
        db: AsyncDatabase,
        collection: str,
        consumer_id: str,
        handler: Handler,
        pipeline: list[dict[str, Any]] | None = None,
    ) -> None:
        self._db = db
        self._collection = collection
        self._consumer_id = consumer_id
        self._handler = handler
        self._pipeline = pipeline or []

    async def run(self) -> None:
        """Vòng lặp watch → handler → lưu resume token. Tự reconnect."""
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError
