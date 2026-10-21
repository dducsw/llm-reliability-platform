"""Atlas Search / Atlas Vector Search index từ `infra/mongo/search/*.json`.

Mỗi file: {"name", "type": "vectorSearch" | "search", "collection", "definition"}.
Chỉ tạo index thiếu (check `listSearchIndexes` trước) → idempotent.

Chú ý: Atlas Search không dùng được trên M0/Flex; khi server không hỗ trợ ta ghi
trạng thái và tiếp tục, không làm fail cả migrate (lần apply lên tier M10+ sẽ
tự điền chỗ thiếu).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)


def _load_specs(directory: Path) -> list[tuple[str, str, str, dict[str, Any]]]:
    """Đọc (đồng bộ) các spec search index — chạy bên trong asyncio.to_thread."""
    if not directory.is_dir():
        return []
    specs: list[tuple[str, str, str, dict[str, Any]]] = []
    for file in sorted(directory.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        specs.append((data["name"], data["type"], data["collection"], data["definition"]))
    return specs


async def _existing(c: AsyncCollection) -> set[str]:
    try:
        cursor = await c.list_search_indexes()
        return {doc["name"] async for doc in cursor}
    except (OperationFailure, AttributeError):
        return set()


async def ensure_search_indexes(db: AsyncDatabase, directory: Path) -> dict[str, str]:
    """Tạo search/vector index từ `*.json`. Trả về {tên_index: trạng thái}."""
    outcomes: dict[str, str] = {}
    for name, type_, collection, definition in await asyncio.to_thread(_load_specs, directory):
        if name in await _existing(db[collection]):
            outcomes[name] = "exists"
            continue
        try:
            await db.command(
                {
                    "createSearchIndexes": collection,
                    "indexes": [{"name": name, "type": type_, "definition": definition}],
                }
            )
            outcomes[name] = "created"
        except OperationFailure as exc:
            detail = exc.details.get("errmsg", exc) if exc.details else exc
            logger.warning("search index %s bị bỏ qua: %s", name, detail)
            outcomes[name] = f"skipped: {detail}"
    return outcomes
