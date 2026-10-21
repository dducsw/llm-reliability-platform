"""Atlas Vector Search / Atlas Search indexes từ infra/mongo/search/*.json."""

from __future__ import annotations

from pathlib import Path

from pymongo.asynchronous.database import AsyncDatabase


async def ensure_search_indexes(db: AsyncDatabase, directory: Path) -> None:
    raise NotImplementedError
