from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    raise NotImplementedError


@router.get("/readyz")
async def readyz() -> dict:
    """Ready khi đã load policy."""
    raise NotImplementedError
