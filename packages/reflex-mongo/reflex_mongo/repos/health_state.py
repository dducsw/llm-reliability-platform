"""Repository cho collection `health_state`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class HealthStateRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db
