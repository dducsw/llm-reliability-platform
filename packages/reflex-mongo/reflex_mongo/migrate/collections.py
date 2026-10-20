"""Tạo Time Series + collection thường (bỏ qua nếu đã tồn tại)."""

from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


async def ensure_collections(db: AsyncDatabase) -> None:
    raise NotImplementedError
