"""Repository cho collection `policies`."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


class PoliciesRepo:
    def __init__(self, db: AsyncDatabase) -> None:
        self._db = db

    async def get(self, route: str) -> dict:
        raise NotImplementedError

    async def list_all(self) -> list[dict]:
        raise NotImplementedError

    async def update_cas(self, route: str, expected_version: int, doc: dict) -> bool:
        """Optimistic concurrency: filter {_id, version: expected}. Ghi kèm policy_history."""
        raise NotImplementedError

    async def history(self, route: str, limit: int = 50) -> list[dict]:
        raise NotImplementedError
