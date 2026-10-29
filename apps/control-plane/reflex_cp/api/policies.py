from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from reflex_mongo.readmodels import (
    get_policy as rm_get_policy,
)
from reflex_mongo.readmodels import (
    get_policy_history as rm_get_policy_history,
)
from reflex_mongo.readmodels import (
    list_policies as rm_list_policies,
)

router = APIRouter()


@router.get("/api/policies")
async def list_policies(request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"policies": []}
    items = await rm_list_policies(db)
    return {"policies": items}


@router.get("/api/policies/{route}")
async def get_policy(route: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    doc = await rm_get_policy(db, route)
    if not doc:
        raise HTTPException(status_code=404, detail="Policy not found")
    return doc


@router.get("/api/policies/{route}/history")
async def policy_history(route: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"history": []}
    items = await rm_get_policy_history(db, route, limit=50)
    return {"history": items}
