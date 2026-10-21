"""Background task: gom batch → insertMany(ordered=False) vào requests_ts / attempts_ts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.events import AttemptEvent, RequestEvent
from reflex_mongo.collections import ATTEMPTS_TS, REQUESTS_TS

from reflex_gateway.telemetry.queue import TelemetryQueue

logger = logging.getLogger(__name__)


class MongoBatchWriter:
    def __init__(
        self,
        db: AsyncDatabase,
        queue: TelemetryQueue,
        batch_size: int = 500,
        flush_ms: int = 250,
    ) -> None:
        self.db = db
        self.queue = queue
        self.batch_size = batch_size
        self.flush_s = flush_ms / 1000.0
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.flush()

    async def run(self) -> None:
        while self._running:
            try:
                await self.flush()
                await asyncio.sleep(self.flush_s)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("MongoBatchWriter flush error: %s", e)
                await asyncio.sleep(self.flush_s)

    async def flush(self) -> None:
        req_batch: list[dict[str, Any]] = []
        att_batch: list[dict[str, Any]] = []

        while not self.queue.empty() and (len(req_batch) + len(att_batch)) < self.batch_size:
            try:
                event = self.queue._queue.get_nowait()
                if isinstance(event, RequestEvent):
                    req_batch.append(event.model_dump(by_alias=True))
                elif isinstance(event, AttemptEvent):
                    att_batch.append(event.model_dump(by_alias=True))
            except asyncio.QueueEmpty:
                break

        if req_batch:
            try:
                await self.db[REQUESTS_TS].insert_many(req_batch, ordered=False)
            except Exception as e:
                logger.error("Error inserting into %s: %s", REQUESTS_TS, e)

        if att_batch:
            try:
                await self.db[ATTEMPTS_TS].insert_many(att_batch, ordered=False)
            except Exception as e:
                logger.error("Error inserting into %s: %s", ATTEMPTS_TS, e)
