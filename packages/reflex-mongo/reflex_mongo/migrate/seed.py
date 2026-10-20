"""Seed từ thư mục seeds/*.yaml (upsert theo _id)."""

from __future__ import annotations

from pathlib import Path

from pymongo.asynchronous.database import AsyncDatabase


async def seed_all(db: AsyncDatabase, directory: Path) -> None:
    raise NotImplementedError
