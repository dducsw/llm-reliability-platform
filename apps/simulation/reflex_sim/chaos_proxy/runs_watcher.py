"""Watch chaos_runs (active) → cập nhật danh sách fault đang áp dụng."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import CHAOS_RUNS

from reflex_sim.chaos_proxy.faults import Fault, FaultSelector, FaultType

logger = logging.getLogger(__name__)


def _as_utc(ts: Any) -> datetime | None:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    return None


class ChaosRunsWatcher:
    def __init__(self, db: AsyncDatabase | None = None) -> None:
        self.db = db
        # (fault, hết hạn): phase ghi `ends_at` nên fault tự tắt nếu scenario runner chết giữa chừng
        self._faults: list[tuple[Fault, datetime | None]] = []
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def active_faults(self) -> list[Fault]:
        now = datetime.now(tz=UTC)
        return [f for f, until in self._faults if until is None or now < until]

    @active_faults.setter
    def active_faults(self, faults: list[Fault]) -> None:
        self._faults = [(f, None) for f in faults]

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

    @staticmethod
    def parse_faults(raw_faults: list[dict[str, Any]]) -> list[Fault]:
        faults: list[Fault] = []
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
        return faults

    @staticmethod
    def latest_phases(active_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Phase mới nhất của mỗi run đang active (phase cũ chỉ được đóng khi cả run kết thúc)."""
        latest: dict[Any, dict[str, Any]] = {}
        for d in active_docs:
            run = d.get("run_id")
            if run not in latest or d.get("phase_index", 0) >= latest[run].get("phase_index", 0):
                latest[run] = d
        return list(latest.values())

    @staticmethod
    def current_faults(active_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [f for d in ChaosRunsWatcher.latest_phases(active_docs) for f in d.get("faults", [])]

    async def refresh(self) -> None:
        """Tính lại từ toàn bộ chaos_runs active — đúng cả khi phase bị đóng bằng update_many
        (event `update` không có fullDocument) hay khi proxy khởi động lại giữa scenario."""
        if self.db is None:
            return
        docs = [d async for d in self.db[CHAOS_RUNS].find({"status": "active"})]
        self._faults = [
            (fault, _as_utc(phase.get("ends_at")))
            for phase in self.latest_phases(docs)
            for fault in self.parse_faults(phase.get("faults", []))
        ]
        logger.info("Active chaos faults updated: %d faults", len(self._faults))

    async def run(self) -> None:
        if self.db is None:
            return
        while self._running:
            try:
                async with await self.db[CHAOS_RUNS].watch() as stream:
                    await self.refresh()
                    async for _change in stream:
                        await self.refresh()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("ChaosRunsWatcher watch interrupted: %s. Reconnecting in 2s...", e)
                await asyncio.sleep(2.0)
