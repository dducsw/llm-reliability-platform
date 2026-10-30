from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from reflex_mongo.readmodels import get_pulse

router = APIRouter()


@router.get("/api/pulse")
async def pulse(request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"health": [], "incidents": [], "policies": []}

    model = await get_pulse(db)
    return model.model_dump()
