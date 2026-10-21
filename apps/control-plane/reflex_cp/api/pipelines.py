from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str) -> dict:
    raise NotImplementedError
