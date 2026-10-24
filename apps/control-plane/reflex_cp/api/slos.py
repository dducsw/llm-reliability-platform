from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from reflex_mongo.collections import SLOS

router = APIRouter()


@router.get("/api/slos")
async def list_slos(request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"slos": []}
    return {"slos": [doc async for doc in db[SLOS].find({}).limit(100)]}


@router.get("/api/slos/{slo_id}")
async def get_slo(slo_id: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    doc = await db[SLOS].find_one({"_id": slo_id}) if db is not None else None
    if doc is None:
        raise HTTPException(status_code=404, detail=f"SLO {slo_id} not found")
    return doc
