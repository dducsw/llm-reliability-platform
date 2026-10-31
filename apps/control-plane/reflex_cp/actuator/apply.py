"""Watch actions (approved) → transaction: update policy CAS + policy_history + outbox event."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import Action, ActionState, Execution
from reflex_core.policy import Policy
from reflex_mongo.collections import ACTIONS, POLICIES, POLICY_HISTORY

from reflex_cp.actuator.transforms import apply_action
from reflex_cp.policy_engine.decision import decide

logger = logging.getLogger(__name__)


class Actuator:
    def __init__(self, db: AsyncDatabase | None = None) -> None:
        self.db = db
        self._running = False

    async def apply(self, action: Action) -> Policy:
        """Áp dụng Action đã duyệt lên Policy với optimistic locking (CAS)."""
        route = action.params.get("route")
        if not route and self.db is not None:
            # Nếu params không có route trực tiếp, thử lấy từ target hoặc policy đầu tiên
            first_p = await self.db[POLICIES].find_one({})
            if first_p:
                route = first_p["_id"]

        if not route:
            raise ValueError(f"Cannot determine route for action: {action.type}")

        if self.db is None:
            # Fallback in-memory
            from reflex_core.policy import Candidate, CandidateRole, default_policy

            current_policy = default_policy(
                route=route,
                candidates=[
                    Candidate(target="mock:primary", weight=0.8, role=CandidateRole.PRIMARY),
                    Candidate(target="mock:secondary", weight=0.2, role=CandidateRole.SECONDARY),
                ],
            )
            new_policy = apply_action(current_policy, action)
            action.state = ActionState.SUCCEEDED
            action.execution = Execution(
                policy_id=route,
                version_before=current_policy.version,
                version_after=new_policy.version,
                applied_at=datetime.now(tz=UTC),
            )
            return new_policy

        now = datetime.now(tz=UTC)
        raw_doc = await self.db[POLICIES].find_one({"_id": route})
        if not raw_doc:
            raise ValueError(f"Policy for route {route} not found")

        current_policy = Policy.model_validate(raw_doc)
        old_version = current_policy.version

        # 1. Snapshot vào policy_history
        await self.db[POLICY_HISTORY].insert_one(
            {
                "policy_id": route,
                "version": old_version,
                "doc": raw_doc,
                "at": now,
            }
        )

        # 2. Tính policy mới
        new_policy = apply_action(current_policy, action)
        new_doc = new_policy.model_dump(by_alias=True, mode="json")

        # 3. CAS replace vào policies
        res = await self.db[POLICIES].replace_one(
            {"_id": route, "version": old_version},
            new_doc,
        )
        if res.modified_count == 0:
            raise RuntimeError(
                f"CAS conflict: policy {route} was modified concurrently (version != {old_version})"
            )

        # 4. Cập nhật action status
        action.state = ActionState.SUCCEEDED
        action.execution = Execution(
            policy_id=route,
            version_before=old_version,
            version_after=new_policy.version,
            applied_at=now,
        )
        action.updated_at = now

        if action.id:
            await self.db[ACTIONS].update_one(
                {"_id": action.id},
                {
                    "$set": {
                        "state": action.state.value,
                        "execution": action.execution.model_dump(mode="json"),
                        "updated_at": now,
                    }
                },
                upsert=True,
            )

        logger.info(
            "Actuator successfully applied %s on route %s (v%d -> v%d)",
            action.type,
            route,
            old_version,
            new_policy.version,
        )
        return new_policy

    async def snapshot_before(self, action: Action) -> dict[str, Any] | None:
        """Snapshot policy ngay trước khi `action` được áp dụng.

        Không tra riêng theo `version`: `reflex-mongo seed` đặt lại version về 1 nên `policy_history` có nhiều
        snapshot cùng version, và `find_one` không sort trả về bản tùy ý (2026-10-30: failback lúc có lúc không
        có baseline). Lấy bản mới nhất có `at` ≤ thời điểm áp dụng.
        """
        if self.db is None or action.execution is None:
            return None
        ex = action.execution
        flt: dict[str, Any] = {"policy_id": ex.policy_id, "version": ex.version_before}
        if ex.applied_at is not None:
            flt["at"] = {"$lte": ex.applied_at}
        async for hist in self.db[POLICY_HISTORY].find(flt).sort("at", -1).limit(1):
            return hist
        return None

    async def rollback(self, action: Action) -> Policy | None:
        """Rollback policy về phiên bản trước của action."""
        if self.db is None or not action.execution:
            return None

        route = action.execution.policy_id
        target_version = action.execution.version_before

        hist = await self.snapshot_before(action)
        if not hist or "doc" not in hist:
            logger.error("No history snapshot found for route %s version %d", route, target_version)
            return None

        restored_doc = hist["doc"]
        restored_policy = Policy.model_validate(restored_doc)
        restored_policy.version = action.execution.version_after + 1
        restored_policy.updated_at = datetime.now(tz=UTC)

        await self.db[POLICIES].replace_one(
            {"_id": route},
            restored_policy.model_dump(by_alias=True, mode="json"),
        )

        action.state = ActionState.ROLLED_BACK
        action.updated_at = datetime.now(tz=UTC)
        if action.id:
            await self.db[ACTIONS].update_one(
                {"_id": action.id},
                {"$set": {"state": action.state.value, "updated_at": action.updated_at}},
            )

        logger.info("Rolled back route %s to content of version %d", route, target_version)
        return restored_policy

    async def handle_proposed(self, action: Action) -> None:
        """Action do Cortex/rules ghi (`proposed`) → policy engine → auto thì áp luôn.

        Chuyển trạng thái bằng CAS trên `state: proposed` nên chỉ một instance xử lý một action.
        """
        if self.db is None:
            return
        decision = await decide(action, self.db)
        now = datetime.now(tz=UTC)
        res = await self.db[ACTIONS].update_one(
            {"_id": action.id, "state": ActionState.PROPOSED.value},
            {
                "$set": {
                    "state": action.state.value,
                    "decision": decision.model_dump(by_alias=True, mode="json"),
                    "updated_at": now,
                }
            },
        )
        if res.modified_count == 0:
            return
        logger.info("Policy engine: action %s → %s", action.id, action.state.value)
        if action.state == ActionState.APPROVED:
            try:
                await self.apply(action)
            except Exception as e:
                logger.error("Error applying action %s: %s", action.id, e)
                await self.db[ACTIONS].update_one(
                    {"_id": action.id},
                    {"$set": {"state": ActionState.FAILED.value, "updated_at": now}},
                )

    async def run(self) -> None:
        """Watch actions: insert `proposed` (Cortex/rules) → policy engine; `approved` → apply."""
        if self.db is None:
            return
        self._running = True
        logger.info("Actuator watcher started")

        while self._running:
            try:
                pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}}]
                async with await self.db[ACTIONS].watch(
                    pipeline,
                    full_document="updateLookup",  # approve = update → cần doc đầy đủ
                ) as stream:
                    async for change in stream:
                        if not self._running:
                            break
                        doc = change.get("fullDocument")
                        if not doc:
                            continue
                        if doc.get("state") == ActionState.PROPOSED:
                            await self.handle_proposed(Action.model_validate(doc))
                        elif doc.get("state") == ActionState.APPROVED:
                            await self.apply(Action.model_validate(doc))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Actuator watch stream interrupted: %s. Retrying in 2s...", e)
                await asyncio.sleep(2)
