"""Seed từ `seeds/*.yaml` — upsert theo `_id` (chạy lại nhiều lần không đổi kết quả).

Chỉ seed catalogue (targets/slos/policies theo DE-1.2). `golden_prompts.yaml`
làm chung với SE và được prober đọc trực tiếp từ file — không nạp vào DB.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Final

import yaml
from pymongo.asynchronous.database import AsyncDatabase

from reflex_mongo.collections import POLICIES, SLOS, TARGETS

FILE_TO_COLLECTION: Final[dict[str, str]] = {
    "targets.yaml": TARGETS,
    "policies.yaml": POLICIES,
    "slos.yaml": SLOS,
}


def _load_files(directory: Path) -> list[tuple[str, list[dict[str, Any]]]]:
    """Đọc (đồng bộ) các file YAML — chạy bên trong asyncio.to_thread."""
    if not directory.is_dir():
        return []
    docs: list[tuple[str, list[dict[str, Any]]]] = []
    for file_name, collection in FILE_TO_COLLECTION.items():
        file = directory / file_name
        if file.exists():
            docs.append((collection, yaml.safe_load(file.read_text(encoding="utf-8"))))
    return docs


async def seed_all(db: AsyncDatabase, directory: Path) -> dict[str, int]:
    """Upsert từng document theo `_id`. Trả về {collection: số document đã seed}."""
    counts: dict[str, int] = {}
    for collection, seeded in await asyncio.to_thread(_load_files, directory):
        for doc in seeded:
            await db[collection].replace_one({"_id": doc["_id"]}, doc, upsert=True)
        counts[collection] = len(seeded)
    return counts
