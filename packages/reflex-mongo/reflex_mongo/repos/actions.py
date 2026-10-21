"""Repository cho collection `actions`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class ActionsRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db

    async def insert(self, action: dict) -> str:
        raise NotImplementedError

    async def transition(self, action_id: str, src: str, dst: str, patch: dict) -> bool:
        raise NotImplementedError

    async def by_incident(self, incident_id: str) -> list[dict]:
        raise NotImplementedError
