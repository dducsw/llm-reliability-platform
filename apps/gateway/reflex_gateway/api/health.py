from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict:
    """Ready khi đã load policy."""
    store = getattr(request.app.state, "policy_store", None)
    ready = store.ready if store else True
    return {"status": "ready" if ready else "not_ready"}
