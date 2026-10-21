"""Áp $jsonSchema validator từ infra/mongo/validators/*.json (sinh từ Pydantic)."""

from __future__ import annotations

from pathlib import Path

from pymongo.asynchronous.database import AsyncDatabase


async def apply_validators(db: AsyncDatabase, directory: Path) -> None:
    raise NotImplementedError
