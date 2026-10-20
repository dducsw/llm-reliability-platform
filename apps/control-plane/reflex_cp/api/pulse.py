from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/pulse")
async def pulse() -> dict:
    raise NotImplementedError
