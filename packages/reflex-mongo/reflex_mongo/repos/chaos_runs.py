"""Repository cho collection `chaos_runs`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class ChaosRunsRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db
