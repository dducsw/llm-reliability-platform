from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/actions")
async def list_actions() -> dict:
    raise NotImplementedError


@router.post("/api/actions")
async def create_action() -> dict:
    raise NotImplementedError


@router.post("/api/actions/{action_id}/approve")
async def approve(action_id: str) -> dict:
    raise NotImplementedError


@router.post("/api/actions/{action_id}/reject")
async def reject(action_id: str) -> dict:
    raise NotImplementedError
