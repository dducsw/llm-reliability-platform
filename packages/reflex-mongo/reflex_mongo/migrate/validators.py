"""Áp $jsonSchema validator cho collection thường (validationLevel: "moderate").

Schema nằm ở `infra/mongo/validators/<collection>.json`, sinh từ Pydantic trong
`reflex-core` bằng `task schemas` (tools/export_schemas.py) - không sửa tay.
Xem docs/30-data/mongodb-data-model.md §6.

Idempotent: `collMod` với cùng validator là no-op.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure


def _load(directory: Path) -> list[tuple[str, dict[str, Any]]]:
    """Đọc (đồng bộ) toàn bộ schema file — chạy bên trong asyncio.to_thread."""
    if not directory.is_dir():
        return []
    return [
        (file.stem, json.loads(file.read_text(encoding="utf-8")))
        for file in sorted(directory.glob("*.json"))
    ]


async def apply_validators(db: AsyncDatabase, directory: Path) -> dict[str, str]:
    """Áp mọi `*.json` (tên file = tên collection). Trả về {collection: trạng thái}."""
    applied: dict[str, str] = {}
    for collection, schema in await asyncio.to_thread(_load, directory):
        try:
            await db.command(
                {
                    "collMod": collection,
                    "validator": schema,
                    "validationLevel": "moderate",
                }
            )
            applied[collection] = "ok"
        except OperationFailure as exc:
            applied[collection] = (
                f"skipped: {exc.details.get('errmsg', exc) if exc.details else exc}"
            )
    return applied
