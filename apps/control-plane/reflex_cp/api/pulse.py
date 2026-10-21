from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from reflex_mongo.collections import HEALTH_STATE, INCIDENTS, POLICIES

router = APIRouter()


@router.get("/api/pulse")
async def pulse(request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"health": [], "incidents": [], "policies": []}

    health_states = []
    async for doc in db[HEALTH_STATE].find({}).limit(100):
        health_states.append(doc)

    open_incidents = []
    async for doc in db[INCIDENTS].find({"is_open": True}).limit(20):
        open_incidents.append(doc)

    policies = []
    async for doc in db[POLICIES].find({}).limit(50):
        policies.append(doc)

    return {
        "health": health_states,
        "incidents": open_incidents,
        "policies": policies,
    }
