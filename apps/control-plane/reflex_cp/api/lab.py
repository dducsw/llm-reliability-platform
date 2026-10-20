from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/api/lab/scenarios/{name}/run")
async def run_scenario(name: str) -> dict:
    raise NotImplementedError
