"""Policy store: load lúc khởi động + Change Stream hot-reload (< 1s) + file snapshot fallback.

Gateway vẫn chạy với snapshot cuối khi Mongo mất kết nối.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml
from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.policy import Policy
from reflex_mongo.collections import POLICIES

logger = logging.getLogger(__name__)


class PolicyStore:
    def __init__(self, db: AsyncDatabase | None = None, seed_file: str = "seeds/policies.yaml") -> None:
        self._db = db
        self._seed_file = Path(seed_file)
        self._policies: dict[str, Policy] = {}
        self._ready = False
        self._watch_task: asyncio.Task | None = None

    async def start(self) -> None:
        await self._load()
        if self._db is not None:
            self._watch_task = asyncio.create_task(self._watch())
        self._ready = True

    async def stop(self) -> None:
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass

    def get(self, route: str) -> Policy | None:
        return self._policies.get(route)

    def set(self, policy: Policy) -> None:
        self._policies[policy.id] = policy

    @property
    def ready(self) -> bool:
        return self._ready

    async def _load(self) -> None:
        loaded = False
        if self._db is not None:
            try:
                cursor = self._db[POLICIES].find({})
                async for doc in cursor:
                    try:
                        p = Policy.model_validate(doc)
                        self._policies[p.id] = p
                        loaded = True
                    except Exception as e:
                        logger.warning("Error parsing policy doc: %s", e)
            except Exception as e:
                logger.warning("Could not load policies from mongo: %s", e)

        if not loaded and self._seed_file.exists():
            try:
                raw_list = yaml.safe_load(self._seed_file.read_text(encoding="utf-8"))
                for raw in raw_list:
                    p = Policy.model_validate(raw)
                    self._policies[p.id] = p
                logger.info("Loaded %d policies from seed file", len(self._policies))
            except Exception as e:
                logger.error("Failed to load policies from seed: %s", e)

    async def _watch(self) -> None:
        if self._db is None:
            return
        while True:
            try:
                async with self._db[POLICIES].watch() as stream:
                    async for change in stream:
                        op = change.get("operationType")
                        if op in ("insert", "replace", "update"):
                            doc = change.get("fullDocument")
                            if doc:
                                try:
                                    p = Policy.model_validate(doc)
                                    self._policies[p.id] = p
                                    logger.info("Hot-reloaded policy for %s v%d", p.id, p.version)
                                except Exception as e:
                                    logger.error("Error validating updated policy: %s", e)
                        elif op == "delete":
                            doc_id = change.get("documentKey", {}).get("_id")
                            if doc_id in self._policies:
                                del self._policies[doc_id]
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Policy change stream interrupted: %s. Reconnecting in 2s...", e)
                await asyncio.sleep(2.0)
