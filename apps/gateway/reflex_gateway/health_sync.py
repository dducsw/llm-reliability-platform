"""Pull health_state định kỳ → input global cho router (score, budget_remaining, open incident)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import HEALTH_STATE

logger = logging.getLogger(__name__)


class HealthSync:
    def __init__(self, db: AsyncDatabase | None = None, interval_s: float = 10.0) -> None:
        self.db = db
        self.interval_s = interval_s
        self._cache: dict[str, dict[str, Any]] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    async def fetch_once(self) -> None:
        if self.db is None:
            return
        try:
            cursor = self.db[HEALTH_STATE].find({})
            new_cache = {}
            async for doc in cursor:
                doc_id = doc.get("_id")
                if doc_id:
                    new_cache[doc_id] = doc
            self._cache = new_cache
        except Exception as e:
            logger.warning("Failed to sync health_state: %s", e)

    async def _loop(self) -> None:
        while self._running:
            await self.fetch_once()
            try:
                await asyncio.sleep(self.interval_s)
            except asyncio.CancelledError:
                break

    async def start(self) -> None:
        self._running = True
        await self.fetch_once()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return dict(self._cache)

    def get(self, key: str) -> dict[str, Any] | None:
        return self._cache.get(key)
