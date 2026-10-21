from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from reflex_core.incident import IncidentStatus
from reflex_mongo.collections import INCIDENTS

router = APIRouter()


@router.get("/api/incidents")
async def list_incidents(
    request: Request,
    is_open: bool | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"incidents": []}

    query: dict[str, Any] = {}
    if is_open is not None:
        query["is_open"] = is_open

    items = []
    async for doc in db[INCIDENTS].find(query).sort("t.detected_at", -1).limit(limit):
        items.append(doc)
    return {"incidents": items}


@router.get("/api/incidents/{key}")
async def get_incident(key: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    doc = await db[INCIDENTS].find_one({"key": key})
    if not doc:
        # Fallback thử _id
        doc = await db[INCIDENTS].find_one({"_id": key})
    if not doc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return doc


@router.post("/api/incidents/{key}/ack")
async def ack(key: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=404, detail="Database not configured")

    now = datetime.now(tz=UTC)
    res = await db[INCIDENTS].update_one(
        {"$or": [{"key": key}, {"_id": key}]},
        {
            "$set": {
                "status": IncidentStatus.INVESTIGATING.value,
                "t.acknowledged_at": now,
                "updated_at": now,
            }
        },
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "status": IncidentStatus.INVESTIGATING.value}


@router.post("/api/incidents/{key}/false-positive")
async def false_positive(key: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=404, detail="Database not configured")

    now = datetime.now(tz=UTC)
    res = await db[INCIDENTS].update_one(
        {"$or": [{"key": key}, {"_id": key}]},
        {
            "$set": {
                "status": IncidentStatus.FALSE_POSITIVE.value,
                "is_open": False,
                "updated_at": now,
            }
        },
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "status": IncidentStatus.FALSE_POSITIVE.value}
