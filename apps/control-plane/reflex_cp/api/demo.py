"""GET /api/demo — trạng thái trình diễn cho Console: profile, scenario đang chạy, time scale
(demo clock "DEMO TIME ×N", console.md §4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from reflex_mongo.collections import CHAOS_RUNS

router = APIRouter()


@router.get("/api/demo")
async def demo_state(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    out: dict[str, Any] = {"profile": settings.reflex_profile, "time_scale": 1.0, "run": None}
    db = getattr(request.app.state, "db", None)
    if db is None:
        return out
    phase = await db[CHAOS_RUNS].find_one({"status": "active"}, sort=[("starts_at", -1)])
    if phase is None:
        return out
    out["time_scale"] = float(phase.get("time_scale") or 1.0)
    out["run"] = {
        "run_id": phase.get("run_id"),
        "scenario": phase.get("scenario"),
        "phase_index": phase.get("phase_index"),
        "phase_starts_at": phase.get("starts_at"),
    }
    first = await db[CHAOS_RUNS].find_one({"run_id": phase.get("run_id"), "phase_index": 0})
    out["run"]["started_at"] = (first or phase).get("starts_at")
    return out
