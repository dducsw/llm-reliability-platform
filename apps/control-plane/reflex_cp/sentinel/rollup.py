"""Tick 10s: chạy A1/A2 (raw → sli_1m), A3 định kỳ (sli_1m → sli_1h)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import ATTEMPTS_TS, REQUESTS_TS, SLI_1M
from reflex_mongo.pipelines import a01_attempt_rollup, a02_request_rollup, a03_hourly_rollup

logger = logging.getLogger(__name__)


class RollupJob:
    def __init__(self, db: AsyncDatabase | None = None, env: str = "local") -> None:
        self.db = db
        self.env = env
        self.last_hour: datetime | None = None

    async def tick(self) -> None:
        if self.db is None:
            return

        now = datetime.now(tz=UTC)
        # Tính lại 3 phút gần nhất để xử lý late data
        from_3m = now - timedelta(minutes=3)

        try:
            # A1: attempts_ts -> sli_1m
            p1 = a01_attempt_rollup.build(now=now, from_=from_3m, to=now, env=self.env)
            await (await self.db[ATTEMPTS_TS].aggregate(p1)).to_list(None)

            # A2: requests_ts -> sli_1m
            p2 = a02_request_rollup.build(now=now, from_=from_3m, to=now, env=self.env)
            await (await self.db[REQUESTS_TS].aggregate(p2)).to_list(None)

            # A3: sli_1m -> sli_1h (chạy khi chuyển sang giờ mới hoặc khởi động)
            curr_hour = now.replace(minute=0, second=0, microsecond=0)
            if self.last_hour is None or curr_hour > self.last_hour:
                hour_from = curr_hour - timedelta(hours=1)
                p3 = a03_hourly_rollup.build(from_=hour_from, to=curr_hour)
                await (await self.db[SLI_1M].aggregate(p3)).to_list(None)
                self.last_hour = curr_hour
        except Exception as e:
            logger.error("Error in RollupJob tick: %s", e)
