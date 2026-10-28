"""Vòng khép kín sau khi áp dụng action: verify (Recovery Proof) → failback 10/50/100 → resolve.

Mỗi lượt quét đọc trạng thái từ Mongo nên chạy lại/khởi động lại an toàn; chuyển trạng thái
incident qua IncidentService (CAS theo status), failback_step đi qua policy engine như mọi action.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import Action, ActionState, ActionType, Verdict
from reflex_core.incident import IncidentStatus
from reflex_mongo.collections import ACTIONS, INCIDENTS, PROBES_TS, SLI_1M

from reflex_cp.incidents.service import IncidentService
from reflex_cp.verifier.failback import FailbackOrchestrator
from reflex_cp.verifier.proof import RecoveryVerifier

logger = logging.getLogger(__name__)

_MITIGATIONS = (
    ActionType.SHIFT_WEIGHT.value,
    ActionType.OPEN_CIRCUIT_GLOBAL.value,
    ActionType.DOWNGRADE_TIER.value,
    ActionType.SHED_PRIORITY.value,
    ActionType.ENABLE_HEDGING.value,
)
_PENDING = (
    ActionState.PROPOSED.value,
    ActionState.AWAITING_APPROVAL.value,
    ActionState.APPROVED.value,
    ActionState.EXECUTING.value,
)
BASELINE_LOOKBACK = timedelta(minutes=15)
HEALTHY_QUALITY = 0.99


def _parse(ts: Any) -> datetime | None:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    if isinstance(ts, str):
        try:
            return _parse(datetime.fromisoformat(ts))
        except ValueError:
            return None
    return None


def _applied_at(action: dict[str, Any]) -> datetime | None:
    return _parse((action.get("execution") or {}).get("applied_at"))


class MitigationLoop:
    def __init__(
        self,
        db: AsyncDatabase,
        verify_after_s: float = 60.0,
        stable_s: float = 60.0,
        min_n: int = 20,
        tick_s: float = 10.0,
    ) -> None:
        self.db = db
        self.verify_after_s = verify_after_s
        self.stable_s = stable_s
        self.min_n = min_n
        self.tick_s = tick_s
        self.verifier = RecoveryVerifier(db)
        self.failback = FailbackOrchestrator(db)
        self.incidents = IncidentService(db)
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.sweep()
            except Exception:
                logger.exception("Mitigation loop sweep failed")
            await asyncio.sleep(self.tick_s)

    def stop(self) -> None:
        self._running = False

    async def sweep(self, now: datetime | None = None) -> list[str]:
        """Một lượt quét; trả về mô tả các chuyển trạng thái đã thực hiện."""
        now = now or datetime.now(tz=UTC)
        statuses = [IncidentStatus.MITIGATING.value, IncidentStatus.MITIGATED.value]
        done: list[str] = []
        async for inc in self.db[INCIDENTS].find({"status": {"$in": statuses}, "is_open": True}):
            step = (
                await self._verify(inc, now)
                if inc["status"] == IncidentStatus.MITIGATING.value
                else await self._failback(inc, now)
            )
            if step:
                done.append(f"{inc['key']}:{step}")
        return done

    async def _latest(self, incident_key: str, types: tuple[str, ...], states: tuple[str, ...]):
        docs = [
            d
            async for d in self.db[ACTIONS].find(
                {
                    "incident_id": incident_key,
                    "type": {"$in": list(types)},
                    "state": {"$in": states},
                }
            )
        ]
        docs.sort(key=lambda d: _applied_at(d) or datetime.min.replace(tzinfo=UTC))
        return docs[-1] if docs else None

    async def _quality(
        self, scope: str, key: str, start: datetime, end: datetime | None = None
    ) -> tuple[int, int]:
        ts: dict[str, Any] = {"$gte": start}
        if end is not None:
            ts["$lt"] = end
        pipeline = [
            {"$match": {"scope": scope, "key": key, "ts": ts}},
            {"$group": {"_id": None, "g": {"$sum": "$q_good"}, "n": {"$sum": "$q_eligible"}}},
        ]
        rows = [r async for r in await self.db[SLI_1M].aggregate(pipeline)]
        return (int(rows[0]["g"]), int(rows[0]["n"])) if rows else (0, 0)

    async def _verify(self, inc: dict[str, Any], now: datetime) -> str | None:
        doc = await self._latest(inc["key"], _MITIGATIONS, (ActionState.SUCCEEDED.value,))
        applied = _applied_at(doc) if doc else None
        if doc is None or applied is None:
            return None
        verdict = (doc.get("verification") or {}).get("verdict")
        if verdict != Verdict.PASS.value:
            if verdict == Verdict.FAIL.value or now < applied + timedelta(
                seconds=self.verify_after_s
            ):
                return None
            route = doc["params"].get("route") or (inc.get("routes") or [None])[0]
            if not route:
                return None
            after_good, after_n = await self._quality("route", route, applied)
            if after_n < self.min_n:
                return None
            detected = _parse((inc.get("t") or {}).get("detected_at")) or applied
            b_good, b_n = await self._quality(
                "route", route, detected - BASELINE_LOOKBACK, detected
            )
            if b_n == 0:  # chưa có baseline: coi như đạt objective
                b_good, b_n = 995, 1000
            result = await self.verifier.verify(
                Action.model_validate(doc),
                baseline_good=b_good,
                baseline_n=b_n,
                after_good=after_good,
                after_n=after_n,
            )
            if result.verdict != Verdict.PASS:
                logger.info("Recovery proof for %s: %s", inc["key"], result.verdict)
                return None
        await self.incidents.transition(
            inc["key"], IncidentStatus.MITIGATED.value, "verifier", str(doc["_id"])
        )
        logger.info("Incident %s mitigated (recovery proof PASS)", inc["key"])
        return "mitigated"

    async def _probes_stable(self, target: str, now: datetime) -> bool:
        since = now - timedelta(seconds=self.stable_s)
        probes = [
            p
            async for p in self.db[PROBES_TS].find(
                {"meta.target": target, "ts": {"$gte": since.replace(tzinfo=None)}}
            )
        ]
        passed = sum(1 for p in probes if (p.get("quality") or {}).get("pass"))
        return len(probes) >= 3 and passed == len(probes)

    async def _failback(self, inc: dict[str, Any], now: datetime) -> str | None:
        parent = await self._latest(
            inc["key"], (ActionType.SHIFT_WEIGHT.value,), (ActionState.SUCCEEDED.value,)
        )
        if parent is None:
            return None
        steps = [
            d
            async for d in self.db[ACTIONS].find(
                {"parent_action_id": parent["_id"], "type": ActionType.FAILBACK_STEP.value}
            )
        ]
        if any(d["state"] in _PENDING for d in steps):
            return None
        done = [d for d in steps if d["state"] == ActionState.SUCCEEDED.value]
        current_pct = max((int(d["params"]["pct"]) for d in done), default=0)
        if current_pct >= 100:
            await self.incidents.transition(
                inc["key"], IncidentStatus.RESOLVED.value, "failback", str(parent["_id"])
            )
            logger.info("Incident %s resolved (failback 100%%)", inc["key"])
            return "resolved"

        origin = parent["params"]["from"]
        last = max((_applied_at(d) for d in [parent, *done] if _applied_at(d)), default=None)
        if last is None or now < last + timedelta(seconds=self.stable_s):
            return None
        if current_pct == 0:
            if not await self._probes_stable(origin, now):
                return None
        else:
            good, n = await self._quality("target", origin, last)
            if n < min(self.min_n, 10) or good / n < HEALTHY_QUALITY:
                return None
        nxt = await self.failback.advance(Action.model_validate(parent), current_pct)
        if nxt is None:
            return None
        logger.info("Failback %s → %s%%", origin, nxt.params.get("pct"))
        return f"failback_{nxt.params.get('pct')}"
