from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/memory/similar")
async def similar() -> dict:
    raise NotImplementedError
