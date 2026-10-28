"""Time Machine API: `POST /api/replays` xếp job, chạy nền trong control-plane; tiến độ và kết quả
nằm trong `replays` → Console nhận qua SSE topic `replays` (time-machine.md §6).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from reflex_mongo.collections import INCIDENTS, REPLAYS

from reflex_cp.timemachine.jobs import run_replay
from reflex_cp.timemachine.variants import VARIANT_DESCRIPTIONS, VARIANTS

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_RUNNING = 2  # DES chạy trên event loop của control-plane → giới hạn job song song


class ReplayRequest(BaseModel):
    incident_id: str
    variants: list[str] = Field(default_factory=lambda: list(VARIANTS))
    k: int = Field(default=20, ge=1, le=100)
    seed: int = 42


def _db(request: Request) -> Any:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    return db


async def execute(db: Any, replay_id: str, req: ReplayRequest) -> None:
    """queued → running → completed | failed. run_replay tự upsert kết quả."""
    await db[REPLAYS].update_one(
        {"_id": replay_id},
        {"$set": {"status": "running", "started_at": datetime.now(tz=UTC)}},
    )
    try:
        await run_replay(
            req.incident_id, req.variants, k=req.k, seed=req.seed, db=db, replay_id=replay_id
        )
    except Exception as e:
        logger.exception("Replay %s failed", replay_id)
        await db[REPLAYS].update_one(
            {"_id": replay_id},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e)[:300],
                    "completed_at": datetime.now(tz=UTC),
                }
            },
        )


@router.get("/api/replays/variants")
async def list_variants() -> dict[str, Any]:
    return {
        "variants": [{"id": v, "description": VARIANT_DESCRIPTIONS.get(v, v)} for v in VARIANTS]
    }


@router.post("/api/replays", status_code=202)
async def create_replay(req: ReplayRequest, request: Request) -> dict[str, Any]:
    db = _db(request)
    unknown = sorted(set(req.variants) - set(VARIANTS))
    if unknown or not req.variants:
        raise HTTPException(status_code=422, detail=f"Unknown variants: {unknown or 'empty'}")
    inc = await db[INCIDENTS].find_one(
        {"$or": [{"key": req.incident_id}, {"_id": req.incident_id}]}
    )
    if inc is None:
        raise HTTPException(status_code=404, detail=f"Incident {req.incident_id} not found")

    tasks: set[asyncio.Task[None]] | None = getattr(request.app.state, "replay_tasks", None)
    if tasks is None:
        tasks = request.app.state.replay_tasks = set()
    if sum(1 for t in tasks if not t.done()) >= MAX_RUNNING:
        raise HTTPException(status_code=429, detail="Too many replays running")

    doc: dict[str, Any] = {
        "_id": f"rp-{uuid.uuid4().hex[:10]}",
        "status": "queued",
        "incident_id": req.incident_id,
        "requested": {"variants": req.variants, "k": req.k, "seed": req.seed},
        "created_at": datetime.now(tz=UTC),
    }
    await db[REPLAYS].insert_one(doc)
    task = asyncio.create_task(execute(db, doc["_id"], req))
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return doc


@router.get("/api/replays")
async def list_replays(
    request: Request, incident_id: str | None = None, limit: int = 20
) -> dict[str, Any]:
    db = _db(request)
    flt = {"incident_id": incident_id} if incident_id else {}
    cursor = db[REPLAYS].find(flt, {"variants.runs": 0}).sort("created_at", -1).limit(limit)
    return {"items": [d async for d in cursor]}


@router.get("/api/replays/{replay_id}")
async def get_replay(replay_id: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    doc = await db[REPLAYS].find_one({"_id": replay_id}) if db is not None else None
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Replay {replay_id} not found")
    return doc
