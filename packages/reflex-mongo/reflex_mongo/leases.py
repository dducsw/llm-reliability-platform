"""Leader lease (collection `leases`) để chỉ một instance chạy Sentinel tick."""

from __future__ import annotations

from datetime import timedelta

from pymongo.asynchronous.database import AsyncDatabase


class Lease:
    def __init__(self, db: AsyncDatabase, name: str, holder: str, ttl: timedelta) -> None:
        self._db = db
        self._name = name
        self._holder = holder
        self._ttl = ttl

    async def acquire_or_renew(self) -> bool:
        raise NotImplementedError

    async def release(self) -> None:
        raise NotImplementedError
