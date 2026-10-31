"""Ghi health_state (watched) cho từng target/route: status, sli, burn, budget, score."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import HEALTH_STATE

logger = logging.getLogger(__name__)


class HealthWriter:
    def __init__(self, db: AsyncDatabase | None = None) -> None:
        self.db = db

    async def write(self, evaluations: list[dict[str, Any]]) -> None:
        """Ghi nhận health_state từ danh sách đánh giá SLO."""
        if not evaluations or self.db is None:
            return

        now = datetime.now(tz=UTC)
        by_key: dict[str, list[dict[str, Any]]] = {}
        for ev in evaluations:
            scope = ev.get("scope", "route")
            key = ev.get("key", "")
            doc_id = f"{scope}:{key}" if not key.startswith(f"{scope}:") else key
            by_key.setdefault(doc_id, []).append(ev)

        for doc_id, ev_list in by_key.items():
            status = "healthy"
            burn_map: dict[str, Any] = {}
            budget_map: dict[str, float] = {}
            any_fires = False

            for ev in ev_list:
                sli = ev.get("sli", "availability")
                b_short = ev.get("burn_short", 0.0)
                b_long = ev.get("burn_long", 0.0)
                fires = ev.get("fires", False)
                burn_map[sli] = {"short": b_short, "long": b_long}

                # budget_remaining: từ evaluation hoặc fallback theo burn
                if "budget_remaining" in ev:
                    budget_map[sli] = round(float(ev["budget_remaining"]), 4)
                else:
                    budget_map[sli] = max(0.0, round(1.0 - (b_long * 0.01), 4)) if fires else 1.0

                if fires:
                    any_fires = True

            if any_fires:
                status = "degraded"

            # Điểm router cơ bản: 1.0 khi healthy, tụt xuống nếu degraded
            score = 0.2 if status == "degraded" else 1.0

            update_doc = {
                "_id": doc_id,
                "status": status,
                "burn": burn_map,
                "budget_remaining": budget_map,
                "score": score,
                "updated_at": now,
            }

            try:
                await self.db[HEALTH_STATE].update_one(
                    {"_id": doc_id},
                    {"$set": update_doc},
                    upsert=True,
                )
            except Exception as e:
                logger.error("Error upserting health_state for %s: %s", doc_id, e)
