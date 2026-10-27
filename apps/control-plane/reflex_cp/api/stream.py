"""GET /api/stream?topics=health,incidents,actions,policies,lab,replays — SSE fan-out từ Change Streams.
Last-Event-ID ↔ resume token.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from reflex_mongo.collections import (
    ACTIONS,
    CHAOS_RUNS,
    HEALTH_STATE,
    INCIDENTS,
    POLICIES,
    REPLAYS,
)

logger = logging.getLogger(__name__)

router = APIRouter()

TOPIC_COLLECTIONS = {
    "health": HEALTH_STATE,
    "incidents": INCIDENTS,
    "actions": ACTIONS,
    "policies": POLICIES,
    "lab": CHAOS_RUNS,
    "replays": REPLAYS,
}
HEARTBEAT_S = 15.0


def encode_token(token: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(token).encode()).decode()


def decode_token(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(value.encode()))
    except Exception:
        return None


def _json_default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


def format_event(topic: str, change: dict[str, Any]) -> str:
    """Một Change Stream event → khung SSE `{topic, op, doc}` (khớp StreamEvent ở Console)."""
    op = change.get("operationType", "update")
    doc = change.get("fullDocument") or {"_id": (change.get("documentKey") or {}).get("_id")}
    body = json.dumps({"topic": topic, "op": op, "doc": doc}, default=_json_default)
    return f"id: {encode_token(change['_id'])}\nevent: change\ndata: {body}\n\n"


async def _pump(
    db: Any, topic: str, resume: dict[str, Any] | None, queue: asyncio.Queue[str]
) -> None:
    kwargs: dict[str, Any] = {"full_document": "updateLookup"}
    if resume:
        kwargs["resume_after"] = resume
    try:
        async with await db[TOPIC_COLLECTIONS[topic]].watch(**kwargs) as stream:
            async for change in stream:
                await queue.put(format_event(topic, change))
    except asyncio.CancelledError:
        raise
    except Exception as e:  # resume token hết hạn, mất kết nối...: client sẽ tự reconnect
        logger.warning("Change stream %s ended: %s", topic, e)
        await queue.put(
            f"event: error\ndata: {json.dumps({'topic': topic, 'detail': str(e)[:120]})}\n\n"
        )


@router.get("/api/stream")
async def stream(
    request: Request,
    topics: str = "health,incidents,actions,policies",
) -> StreamingResponse:
    wanted = [t for t in (x.strip() for x in topics.split(",")) if t in TOPIC_COLLECTIONS]
    resume = decode_token(request.headers.get("last-event-id"))
    db = getattr(request.app.state, "db", None)

    async def event_generator() -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
        tasks = (
            [asyncio.create_task(_pump(db, t, resume, queue)) for t in wanted]
            if db is not None
            else []
        )
        try:
            yield f"event: connected\ndata: {json.dumps({'topics': wanted})}\n\n"
            while not await request.is_disconnected():
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_S)
                except TimeoutError:
                    yield f"event: ping\ndata: {json.dumps({'ts': asyncio.get_running_loop().time()})}\n\n"
        finally:
            for t in tasks:
                t.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
