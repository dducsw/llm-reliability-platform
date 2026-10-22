from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

from fastapi import APIRouter, HTTPException, Request
from reflex_mongo.collections import REPLAYS

router = APIRouter()


@router.post("/api/replays", status_code=202)
async def create_replay(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Xếp job Time Machine; worker (DE) nhận job `queued` và cập nhật tiến độ."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    doc = {
        "_id": f"rp-{uuid.uuid4().hex[:10]}",
        "status": "queued",
        "incident_id": payload.get("incident_id"),
        "variants": payload.get("variants", []),
        "seeds": payload.get("seeds", 20),
        "created_at": datetime.now(tz=UTC),
    }
    await db[REPLAYS].insert_one(doc)
    return doc


@router.get("/api/replays/{replay_id}")
async def get_replay(replay_id: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    doc = await db[REPLAYS].find_one({"_id": replay_id}) if db is not None else None
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Replay {replay_id} not found")
    return doc
