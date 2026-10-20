"""Repository cho collection `investigations`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class InvestigationsRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db
