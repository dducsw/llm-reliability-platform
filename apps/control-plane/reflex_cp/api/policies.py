from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from reflex_mongo.collections import POLICIES, POLICY_HISTORY

router = APIRouter()


@router.get("/api/policies")
async def list_policies(request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"policies": []}
    items = []
    async for doc in db[POLICIES].find({}):
        items.append(doc)
    return {"policies": items}


@router.get("/api/policies/{route}")
async def get_policy(route: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    doc = await db[POLICIES].find_one({"_id": route})
    if not doc:
        raise HTTPException(status_code=404, detail="Policy not found")
    return doc


@router.get("/api/policies/{route}/history")
async def policy_history(route: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"history": []}
    items = []
    async for doc in db[POLICY_HISTORY].find({"policy_id": route}).sort("version", -1).limit(50):
        items.append(doc)
    return {"history": items}
