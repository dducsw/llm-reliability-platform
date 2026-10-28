"""Watchdog R4: Cortex chết/treo → control-plane tự chạy rule engine cho incident bị bỏ rơi.

- `detected` quá `unclaimed_s` (không Cortex nào nhận)            → reason `unclaimed`
- `investigating` quá `stale_s` kể từ `investigating_since`      → reason `stale`
Claim bằng update có điều kiện (status + investigating_since chưa đổi) nên không tranh với
Cortex còn sống; action đi đúng đường cũ (proposed → policy engine → guardrails → actuator).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import Action, ActionState, ActionType, ProposedBy, validate_params
from reflex_core.incident import Diagnosis, IncidentStatus, Side, TimelineEntry
from reflex_core.rules import RULES_CONFIDENCE, classify
from reflex_mongo.collections import ACTIONS, INCIDENTS, OUTBOX, POLICIES

logger = logging.getLogger(__name__)

INVESTIGATOR = "rules@control-plane"


def _parse(ts: Any) -> datetime | None:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    if isinstance(ts, str):
        try:
            return _parse(datetime.fromisoformat(ts))
        except ValueError:
            return None
    return None


class CortexWatchdog:
    def __init__(
        self,
        db: AsyncDatabase,
        unclaimed_s: float = 60.0,
        stale_s: float = 180.0,
        tick_s: float = 10.0,
    ) -> None:
        self.db = db
        self.unclaimed_s = unclaimed_s
        self.stale_s = stale_s
        self.tick_s = tick_s
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.sweep()
            except Exception:
                logger.exception("Cortex watchdog sweep failed")
            await asyncio.sleep(self.tick_s)

    def stop(self) -> None:
        self._running = False

    def _abandoned(self, doc: dict[str, Any], now: datetime) -> tuple[str, dict[str, Any]] | None:
        """(reason, filter claim) nếu incident bị bỏ rơi; filter khớp đúng trạng thái đã đọc."""
        status = doc.get("status")
        if status == IncidentStatus.DETECTED.value:
            detected_at = _parse((doc.get("t") or {}).get("detected_at"))
            if detected_at and now - detected_at > timedelta(seconds=self.unclaimed_s):
                return "unclaimed", {"key": doc["key"], "status": status}
        elif status == IncidentStatus.INVESTIGATING.value:
            since_raw = doc.get("investigating_since")
            # Claim cũ (trước lease) không có investigating_since → tính từ lúc detected
            since = _parse(since_raw) or _parse((doc.get("t") or {}).get("detected_at"))
            if since and now - since > timedelta(seconds=self.stale_s):
                return "stale", {
                    "key": doc["key"],
                    "status": status,
                    "investigating_since": since_raw,
                }
        return None

    async def sweep(self, now: datetime | None = None) -> list[str]:
        """Một lượt quét; trả về key các incident watchdog đã xử lý."""
        now = now or datetime.now(tz=UTC)
        statuses = [IncidentStatus.DETECTED.value, IncidentStatus.INVESTIGATING.value]
        docs = [d async for d in self.db[INCIDENTS].find({"status": {"$in": statuses}})]
        handled: list[str] = []
        for doc in docs:
            found = self._abandoned(doc, now)
            if found is None:
                continue
            reason, flt = found
            if await self._claim(flt, reason, now):
                await self._fallback(doc, reason, now)
                handled.append(doc["key"])
        return handled

    async def _claim(self, flt: dict[str, Any], reason: str, now: datetime) -> bool:
        entry = TimelineEntry(at=now, kind=f"cortex_fallback:{reason}", actor=INVESTIGATOR)
        res = await self.db[INCIDENTS].update_one(
            flt,
            {
                "$set": {
                    "status": IncidentStatus.INVESTIGATING.value,
                    "investigator": INVESTIGATOR,
                    "investigating_since": now.isoformat(),
                },
                "$push": {"timeline": entry.model_dump(mode="json")},
            },
        )
        return res.modified_count == 1

    async def _fallback(self, incident: dict[str, Any], reason: str, now: datetime) -> None:
        key = incident["key"]
        routes = incident.get("routes") or []
        policy = (await self.db[POLICIES].find_one({"_id": routes[0]})) if routes else None
        rec = classify({"incident": incident, "policy": policy or {}})

        diag = Diagnosis(
            side=Side.UNKNOWN,
            hypothesis=f"Cortex offline ({reason}); rule-based: "
            f"{rec.action_type if rec else 'none'}",
            confidence=RULES_CONFIDENCE,
            by=INVESTIGATOR,
        )
        await self.db[INCIDENTS].update_one(
            {"key": key, "investigator": INVESTIGATOR},
            {
                "$set": {
                    "diagnosis": diag.model_dump(mode="json"),
                    "status": IncidentStatus.MITIGATING.value,
                }
            },
        )

        action_id = None
        if rec is not None:
            action_id = await self._propose(key, rec.action_type, rec.params, now)
        await self._event(incident, reason, rec.action_type if rec else None, action_id, now)
        logger.warning(
            "Cortex fallback (%s) for incident %s → %s",
            reason,
            key,
            rec.action_type if rec else "none",
        )

    async def _propose(
        self, incident_key: str, action_type: str, params: dict[str, Any], now: datetime
    ) -> str:
        act_type = ActionType(action_type)
        validate_params(act_type, params)
        action = Action(
            _id=f"act-{now.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}",
            incident_id=incident_key,
            type=act_type,
            params=params,
            state=ActionState.PROPOSED,
            proposed_by=ProposedBy(actor="rules", confidence=RULES_CONFIDENCE),
            created_at=now,
            updated_at=now,
        )
        await self.db[ACTIONS].insert_one(action.model_dump(by_alias=True, mode="json"))
        return str(action.id)

    async def _event(
        self,
        incident: dict[str, Any],
        reason: str,
        action_type: str | None,
        action_id: str | None,
        now: datetime,
    ) -> None:
        """Datadog event qua outbox: `reflex.cortex.fallback` để monitor/đếm số lần Cortex offline."""
        await self.db[OUTBOX].insert_one(
            {
                "_id": f"obx-{uuid.uuid4().hex[:12]}",
                "kind": "cortex_fallback",
                "status": "pending",
                "attempts": 0,
                "next_at": now,
                "created_at": now,
                "payload": {
                    "title": f"Cortex offline — rules fallback for {incident['key']}",
                    "text": f"reason={reason} action={action_type or 'none'} "
                    f"action_id={action_id or '-'}",
                    "tags": [
                        "reflex.cortex.fallback",
                        f"reason:{reason}",
                        f"incident:{incident['key']}",
                        f"action_type:{action_type or 'none'}",
                    ],
                    "alert_type": "warning",
                },
            }
        )
