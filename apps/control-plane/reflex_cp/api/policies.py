from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/policies")
async def list_policies() -> dict:
    raise NotImplementedError


@router.get("/api/policies/{route}/history")
async def policy_history(route: str) -> dict:
    raise NotImplementedError
