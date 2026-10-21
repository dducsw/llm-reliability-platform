"""Repository cho collection `outbox`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class OutboxRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db
