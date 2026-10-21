"""Repository cho collection `replays`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class ReplaysRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db
