"""Repository cho collection `slos`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class SlosRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db
