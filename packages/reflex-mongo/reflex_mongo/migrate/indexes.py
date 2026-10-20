"""Index thường, TTL, partial unique (incidents.dedup_key), unique sli_1m{scope,key,env,ts}."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


async def ensure_indexes(db: AsyncDatabase) -> None:
    raise NotImplementedError
