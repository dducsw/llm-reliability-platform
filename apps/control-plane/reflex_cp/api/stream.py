"""GET /api/stream?topics=health,incidents,actions,policies,lab — SSE fan-out từ Change Streams.
Last-Event-ID ↔ resume token."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/stream")
async def stream(request: Request, topics: str = "health,incidents,actions,policies"):  # type: ignore[no-untyped-def]
    raise NotImplementedError
