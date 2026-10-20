"""Repository cho collection `postmortems`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class PostmortemsRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db
