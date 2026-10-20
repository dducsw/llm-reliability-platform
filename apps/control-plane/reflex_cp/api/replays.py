from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/api/replays")
async def create_replay() -> dict:
    raise NotImplementedError


@router.get("/api/replays/{replay_id}")
async def get_replay(replay_id: str) -> dict:
    raise NotImplementedError
