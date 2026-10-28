"""Action có `duration_s` (shift_weight do rules tự áp dụng) hết hạn → rollback policy."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import Action, ActionState, ActionType
from reflex_mongo.collections import ACTIONS, POLICIES

from reflex_cp.actuator.apply import Actuator

logger = logging.getLogger(__name__)


def _parse(ts: Any) -> datetime | None:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    if isinstance(ts, str):
        try:
            return _parse(datetime.fromisoformat(ts))
        except ValueError:
            return None
    return None


class ActionExpirer:
    def __init__(self, db: AsyncDatabase, actuator: Actuator | None = None, tick_s: float = 10.0):
        self.db = db
        self.actuator = actuator or Actuator(db)
        self.tick_s = tick_s
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.sweep()
            except Exception:
                logger.exception("Action expiry sweep failed")
            await asyncio.sleep(self.tick_s)

    def stop(self) -> None:
        self._running = False

    async def sweep(self, now: datetime | None = None) -> list[str]:
        """Rollback action đã hết hạn; trả về id đã rollback."""
        now = now or datetime.now(tz=UTC)
        query = {
            "state": ActionState.SUCCEEDED.value,
            "type": ActionType.SHIFT_WEIGHT.value,
            "params.duration_s": {"$gt": 0},
        }
        done: list[str] = []
        async for doc in self.db[ACTIONS].find(query):
            execution = doc.get("execution") or {}
            applied_at = _parse(execution.get("applied_at"))
            if applied_at is None:
                continue
            if now < applied_at + timedelta(seconds=int(doc["params"]["duration_s"])):
                continue
            policy = await self.db[POLICIES].find_one({"_id": execution.get("policy_id")})
            if policy is None or policy.get("version") != execution.get("version_after"):
                # Policy đã bị action khác sửa tiếp: rollback sẽ ghi đè → không tự động làm
                await self.db[ACTIONS].update_one(
                    {"_id": doc["_id"]}, {"$set": {"params.duration_s": 0}}
                )
                logger.warning(
                    "Action %s expired but policy changed since; skip rollback", doc["_id"]
                )
                continue
            if await self.actuator.rollback(Action.model_validate(doc)) is not None:
                logger.info(
                    "Action %s expired after %ss → rolled back",
                    doc["_id"],
                    doc["params"]["duration_s"],
                )
                done.append(str(doc["_id"]))
        return done
