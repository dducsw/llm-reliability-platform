"""Vòng lặp Sentinel (chỉ chạy khi giữ lease)."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.leases import Lease

from reflex_cp.incidents.service import IncidentService
from reflex_cp.sentinel.burn import BurnEvaluator
from reflex_cp.sentinel.detector import Detector
from reflex_cp.sentinel.health import HealthWriter
from reflex_cp.sentinel.rollup import RollupJob
from reflex_cp.settings import Settings

logger = logging.getLogger(__name__)


class Sentinel:
    def __init__(
        self,
        db: AsyncDatabase,
        settings: Settings | None = None,
        rollup_job: RollupJob | None = None,
        burn_evaluator: BurnEvaluator | None = None,
        health_writer: HealthWriter | None = None,
        detector: Detector | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or Settings()
        self.tick_s = self.settings.sentinel_tick_s
        self.lease = Lease(
            db=db,
            name="sentinel",
            holder=self.settings.instance_id,
            ttl=timedelta(seconds=max(self.tick_s * 2, 10)),
        )
        self.rollup = rollup_job or RollupJob(db)
        self.burn = burn_evaluator or BurnEvaluator(db, profile=self.settings.reflex_profile)
        self.health = health_writer or HealthWriter(db)
        self.detector = detector or Detector(IncidentService(db))
        self._running = False

    async def tick(self) -> list[dict[str, Any]]:
        """Một nhịp kiểm tra Sentinel: acquire lease → rollup → burn eval → health → detector."""
        acquired = await self.lease.acquire_or_renew()
        if not acquired:
            logger.debug("Sentinel lease not held by %s; skipping tick", self.settings.instance_id)
            return []

        try:
            # 1. Rollup 1m & 1h
            await self.rollup.tick()

            # 2. Đánh giá burn rate các SLO
            evaluations = await self.burn.evaluate()

            # 3. Ghi health_state
            await self.health.write(evaluations)

            # 4. Mở/gộp incident nếu vi phạm
            incidents = await self.detector.detect(evaluations)
            return incidents
        except Exception as e:
            logger.error("Error during Sentinel tick: %s", e)
            return []

    async def run(self) -> None:
        """Chạy vòng lặp vô tận theo chu kỳ tick_s."""
        self._running = True
        logger.info(
            "Sentinel loop started (interval=%.1fs, instance=%s)",
            self.tick_s,
            self.settings.instance_id,
        )
        while self._running:
            try:
                await self.tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Unexpected error in Sentinel loop: %s", e)

            try:
                await asyncio.sleep(self.tick_s)
            except asyncio.CancelledError:
                break

        await self.lease.release()
        logger.info("Sentinel loop stopped and lease released")

    def stop(self) -> None:
        self._running = False
