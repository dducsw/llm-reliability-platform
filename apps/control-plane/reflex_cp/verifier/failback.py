"""Failback từng nấc 10% → 50% → 100% khi target gốc ổn định ≥ N phút."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import (
    Action,
    ActionState,
    ActionType,
    FailbackStepParams,
    ProposedBy,
    new_action_id,
)
from reflex_mongo.collections import ACTIONS

logger = logging.getLogger(__name__)


class FailbackOrchestrator:
    def __init__(self, db: AsyncDatabase | None = None) -> None:
        self.db = db
        self.steps = [10, 50, 100]

    def create_step_action(
        self,
        parent_action: Action,
        route: str,
        to_target: str,
        pct: int,
    ) -> Action:
        """Sinh ra action con failback_step cho từng nấc tỷ lệ."""
        now = datetime.now(tz=UTC)
        return Action(
            _id=new_action_id(now),
            incident_id=parent_action.incident_id,
            parent_action_id=parent_action.id,
            type=ActionType.FAILBACK_STEP,
            params=FailbackStepParams(
                route=route,
                to=to_target,
                pct=pct,
            ).model_dump(mode="json"),
            state=ActionState.PROPOSED,
            proposed_by=ProposedBy(actor="failback_orchestrator"),
            created_at=now,
            updated_at=now,
        )

    async def advance(self, parent_action: Action, current_pct: int) -> Action | None:
        """Tìm nấc tiếp theo (10 -> 50 -> 100)."""
        idx = self.steps.index(current_pct) if current_pct in self.steps else -1
        if idx + 1 < len(self.steps):
            next_pct = self.steps[idx + 1]
            route = parent_action.params.get("route", "")
            target = parent_action.params.get("from", "")
            next_act = self.create_step_action(parent_action, route, target, next_pct)
            if self.db is not None:
                doc = next_act.model_dump(by_alias=True, mode="json")
                doc["created_at"], doc["updated_at"] = next_act.created_at, next_act.updated_at
                await self.db[ACTIONS].insert_one(doc)
            return next_act
        return None

    async def run(self) -> None:
        pass
