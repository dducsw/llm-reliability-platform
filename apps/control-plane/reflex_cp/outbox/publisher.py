"""Outbox publisher: lấy doc `pending`, gửi Datadog event, đánh dấu `sent` (at-least-once)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from reflex_mongo.collections import OUTBOX
from reflex_telemetry.datadog_api import DatadogApi

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(300, 2**attempts))


class OutboxPublisher:
    def __init__(self, db: Any, datadog: DatadogApi | None, poll_s: float = 2.0) -> None:
        self._db = db
        self._datadog = datadog
        self._poll_s = poll_s
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                while await self.process_once():
                    pass
            except Exception:
                logger.exception("Outbox publisher tick failed")
            await asyncio.sleep(self._poll_s)

    def stop(self) -> None:
        self._running = False

    async def process_once(self) -> bool:
        """Claim một doc đến hạn; trả True nếu có doc được xử lý."""
        now = datetime.now(tz=UTC)
        doc = await self._db[OUTBOX].find_one_and_update(
            {"status": "pending", "next_at": {"$lte": now}},
            {"$set": {"status": "sending"}, "$inc": {"attempts": 1}},
        )
        if doc is None:
            return False
        try:
            if self._datadog is None:
                raise RuntimeError("Datadog API not configured")
            event = doc.get("payload", {})
            await self._datadog.send_event(
                title=event.get("title", doc.get("kind", "reflex")),
                text=event.get("text", ""),
                tags=event.get("tags", []),
                alert_type=event.get("alert_type", "info"),
            )
            update: dict[str, Any] = {"status": "sent", "sent_at": datetime.now(tz=UTC)}
        except Exception as e:
            attempts = doc.get("attempts", 0) + 1
            logger.warning("Outbox %s failed (attempt %d): %s", doc["_id"], attempts, e)
            update = {
                "status": "failed" if attempts >= MAX_ATTEMPTS else "pending",
                "next_at": datetime.now(tz=UTC) + _backoff(attempts),
                "last_error": str(e)[:200],
            }
        await self._db[OUTBOX].update_one({"_id": doc["_id"]}, {"$set": update})
        return True
