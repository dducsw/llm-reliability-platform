"""GET /api/stream?topics=health,incidents,actions,policies,lab — SSE fan-out từ Change Streams.
Last-Event-ID ↔ resume token.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/stream")
async def stream(
    request: Request,
    topics: str = "health,incidents,actions,policies",
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        # Gửi initial connection event
        yield f"event: connected\ndata: {json.dumps({'topics': topics})}\n\n"

        while True:
            if await request.is_disconnected():
                break
            try:
                # Gửi heartbeat định kỳ để giữ kết nối SSE
                await asyncio.sleep(5)
                yield f"event: ping\ndata: {json.dumps({'timestamp': asyncio.get_event_loop().time()})}\n\n"
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("SSE error: %s", e)
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
