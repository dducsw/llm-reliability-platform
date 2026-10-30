from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError
from reflex_core.incident import (
    Incident,
    IncidentStatus,
    IncidentTimes,
    Severity,
    Signal,
    TimelineEntry,
)
from reflex_mongo.collections import INCIDENTS
from reflex_mongo.serde import to_doc

logger = logging.getLogger(__name__)


class IncidentService:
    # Gắn một lần ở main (DogStatsD dùng chung); None khi không có telemetry (test, CLI)
    statsd: Any = None

    def __init__(self, db: AsyncDatabase | None = None) -> None:
        self.db = db
        self._memory_incidents: dict[str, dict[str, Any]] = {}

    async def open_or_merge(
        self,
        signal: dict[str, Any],
        slo_id: str,
        target: str | None = None,
        route: str | None = None,
        severity: Severity = Severity.CRITICAL,
        sli: str = "quality",
    ) -> dict[str, Any]:
        """Tạo incident mới hoặc gộp signal vào incident đang mở (chống trùng lặp qua dedup_key)."""
        now = datetime.now(tz=UTC)
        # Không chứa slo_id/nguồn: Sentinel (`target:…:quality`) và Datadog (`dd:<monitor>`) cùng thấy
        # một sự cố trên {target, route, sli} phải gộp vào một incident, nếu không sẽ mitigation chồng nhau.
        dedup_key = f"{sli}:{target or '*'}:{route or '*'}"
        sig_model = Signal(
            source=signal.get("source", "sentinel"),
            at=signal.get("at") or now,
            burn=signal.get("burn"),
            monitor_id=signal.get("monitor_id"),
            alert_id=signal.get("alert_id"),
            diagnosis=signal.get("diagnosis"),
        )

        if self.statsd is not None:
            self.statsd.increment("reflex.incident.signal", tags=[f"source:{sig_model.source}"])

        if self.db is not None:
            # Tìm incident đang mở có cùng dedup_key; không có thì incident đang mở trên cùng route —
            # một route một incident: M7 (chỉ group theo route) và Sentinel (target+route) cùng thấy một
            # silent-brownout, tách ra hai incident là hai shift_weight chồng nhau (2026-10-30 05:09).
            existing = await self.db[INCIDENTS].find_one({"dedup_key": dedup_key, "is_open": True})
            if existing is None and route:
                existing = await self.db[INCIDENTS].find_one({"routes": route, "is_open": True})
            if existing:
                await self.db[INCIDENTS].update_one(
                    {"_id": existing["_id"]},
                    {"$push": {"signals": to_doc(sig_model)}},
                )
                logger.info("Merged signal into active incident %s", existing.get("key"))
                return existing

            inc_key = f"INC-{now.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"
            new_inc = Incident(
                key=inc_key,
                dedup_key=dedup_key,
                is_open=True,
                slo_id=slo_id,
                scope="target_route" if target and route else ("route" if route else "target"),
                target=target,
                routes=[route] if route else [],
                sli=sli,
                severity=severity,
                status=IncidentStatus.DETECTED,
                signals=[sig_model],
                t=IncidentTimes(first_bad_at=now, detected_at=now),
                created_at=now,
            )
            doc = to_doc(new_inc)  # datetime giữ BSON Date để sort("t.detected_at") không lẫn kiểu
            doc["_id"] = inc_key
            try:
                await self.db[INCIDENTS].insert_one(doc)
                logger.info("Opened new incident %s (dedup=%s)", inc_key, dedup_key)
                if self.statsd is not None:  # M12: so sánh số incident theo nguồn phát hiện
                    self.statsd.increment(
                        "reflex.incident.open", tags=[f"source:{sig_model.source}"]
                    )
                return doc
            except DuplicateKeyError:
                # Race condition: một tiến trình khác vừa tạo xong
                found = await self.db[INCIDENTS].find_one({"dedup_key": dedup_key, "is_open": True})
                return found or doc
        else:
            # In-memory fallback
            for inc in self._memory_incidents.values():
                same = inc.get("dedup_key") == dedup_key or (
                    route and route in inc.get("routes", [])
                )
                if same and inc.get("is_open"):
                    inc["signals"].append(sig_model.model_dump(mode="json"))
                    return inc

            inc_key = f"INC-{now.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"
            doc = {
                "_id": inc_key,
                "key": inc_key,
                "dedup_key": dedup_key,
                "is_open": True,
                "slo_id": slo_id,
                "scope": "target_route" if target and route else "route",
                "target": target,
                "routes": [route] if route else [],
                "sli": sli,
                "severity": severity.value,
                "status": IncidentStatus.DETECTED.value,
                "signals": [sig_model.model_dump(mode="json")],
                "t": {"first_bad_at": now.isoformat(), "detected_at": now.isoformat()},
            }
            self._memory_incidents[inc_key] = doc
            return doc

    async def transition(self, key: str, status: str, actor: str, ref: str | None = None) -> None:
        new_status = IncidentStatus(status)
        now = datetime.now(tz=UTC)
        entry = TimelineEntry(at=now, kind="status_change", actor=actor, ref=ref)

        fields: dict[str, Any] = {"status": new_status.value}
        if new_status in (IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE):
            fields["is_open"] = False
            fields["t.resolved_at"] = now
        elif new_status == IncidentStatus.MITIGATED:
            fields["t.mitigated_at"] = now

        if self.db is not None:
            await self.db[INCIDENTS].update_one(
                {"key": key},
                {"$set": fields, "$push": {"timeline": to_doc(entry)}},
            )
        elif key in self._memory_incidents:
            self._memory_incidents[key].update(fields)

    async def compute_signature(self, key: str) -> None:
        """A8 first-bad-at + A9 signature vector."""
        pass

    async def compute_impact(self, key: str) -> None:
        """A13 blast radius."""
        pass
