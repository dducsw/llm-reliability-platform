"""Repository cho collection `targets`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class TargetsRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db
