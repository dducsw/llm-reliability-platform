"""Repository cho collection `incidents`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class IncidentsRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db

    async def open_or_merge(self, incident: dict, signal: dict) -> tuple[dict, bool]:
        """Insert với partial unique dedup_key; DuplicateKey → $push signal vào incident đang mở."""
        raise NotImplementedError

    async def transition(self, key: str, status: str, entry: dict) -> None:
        raise NotImplementedError

    async def get_by_key(self, key: str) -> dict | None:
        raise NotImplementedError

    async def list(self, status: str | None = None, sli: str | None = None) -> list[dict]:
        raise NotImplementedError
