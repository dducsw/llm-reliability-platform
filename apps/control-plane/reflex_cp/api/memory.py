from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from reflex_mongo.collections import INCIDENTS
from reflex_mongo.pipelines import a10_similar_incidents

router = APIRouter()


@router.get("/api/memory/similar")
async def similar(incident_id: str, request: Request, k: int = 5) -> dict[str, Any]:
    """Sự cố tương tự (A10) cho một incident: vector signature + thống kê hiệu quả action."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    incident = await db[INCIDENTS].find_one({"_id": incident_id})
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    vec = (incident.get("signature") or {}).get("vec")
    if not vec:
        return {"incident_id": incident_id, "similar": [], "reason": "no_signature"}
    pipeline = a10_similar_incidents.build(
        vec=vec, sli=incident["sli"], scope=incident.get("scope"), k=k, current_id=incident_id
    )
    return {
        "incident_id": incident_id,
        "similar": [doc async for doc in await db[INCIDENTS].aggregate(pipeline)],
    }
