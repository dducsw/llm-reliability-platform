from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/slos")
async def list_slos() -> dict:
    raise NotImplementedError


@router.get("/api/slos/{slo_id}")
async def get_slo(slo_id: str) -> dict:
    raise NotImplementedError
