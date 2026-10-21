"""Watch chaos_runs (active) → cập nhật danh sách fault đang áp dụng."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import CHAOS_RUNS

from reflex_sim.chaos_proxy.faults import Fault, FaultSelector, FaultType

logger = logging.getLogger(__name__)


class ChaosRunsWatcher:
    def __init__(self, db: AsyncDatabase | None = None) -> None:
        self.db = db
        self.active_faults: list[Fault] = []
        self._running = False
        self._task: asyncio.Task | None = None

    def set_faults(self, faults: list[Fault]) -> None:
        """Cập nhật trực tiếp danh sách fault (dùng trong test hoặc scenario runner)."""
        self.active_faults = list(faults)

    async def start(self) -> None:
        self._running = True
        if self.db is not None:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run(self) -> None:
        if self.db is None:
            return
        while self._running:
            try:
                async with self.db[CHAOS_RUNS].watch() as stream:
                    async for change in stream:
                        op = change.get("operationType")
                        if op in ("insert", "replace", "update"):
                            doc = change.get("fullDocument")
                            if doc and doc.get("status") == "active":
                                raw_faults = doc.get("faults", [])
                                faults = []
                                for rf in raw_faults:
                                    try:
                                        faults.append(
                                            Fault(
                                                type=FaultType(rf["type"]),
                                                selector=FaultSelector(
                                                    target=rf.get("target", "*"),
                                                    route=rf.get("route"),
                                                    pct_of_traffic=rf.get("pct_of_traffic"),
                                                ),
                                                params=rf.get("params", {}),
                                            )
                                        )
                                    except Exception as exc:
                                        logger.warning("Error parsing fault: %s", exc)
                                self.active_faults = faults
                                logger.info("Active chaos faults updated: %d faults", len(faults))
                        elif op == "delete":
                            self.active_faults = []
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("ChaosRunsWatcher watch interrupted: %s. Reconnecting in 2s...", e)
                await asyncio.sleep(2.0)
