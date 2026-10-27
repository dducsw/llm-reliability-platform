"""POST /v1/chat/completions — OpenAI-compatible (docs/60-interface/api-contracts.md §1).

Headers vào: x-reflex-route (bắt buộc), x-priority, x-reflex-session, x-reflex-deadline-ms.
Headers ra:  x-reflex-target, x-reflex-attempts, x-reflex-policy-version,
             x-reflex-request-id, x-reflex-quality, x-reflex-overhead-ms (wall − upstream, SE-9.2).
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from reflex_gateway.engine.orchestrator import Orchestrator, OrchestratorResult, RequestContext

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    orchestrator: Orchestrator = request.app.state.orchestrator
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from None

    route = request.headers.get("x-reflex-route") or payload.get("model")
    if not route:
        raise HTTPException(
            status_code=400, detail="Missing x-reflex-route header or model in payload"
        )

    priority = int(request.headers.get("x-priority", "1"))
    session = request.headers.get("x-reflex-session")
    deadline_ms = int(request.headers.get("x-reflex-deadline-ms", "8000"))
    request_id = request.headers.get("x-reflex-request-id") or f"req-{uuid.uuid4().hex[:12]}"
    trace_id = request.headers.get("x-datadog-trace-id")

    ctx = RequestContext(
        request_id=request_id,
        route=route,
        priority=priority,
        session=session,
        deadline_ms=deadline_ms,
        trace_id=trace_id,
    )

    is_stream = bool(payload.get("stream", False))
    if is_stream:
        if orchestrator.should_shed(route, priority):
            # Trả 503 thật thay vì mở SSE rồi mới báo lỗi.
            return _shed_response(orchestrator.shed(ctx))

        async def event_generator() -> AsyncIterator[str]:
            async for chunk in orchestrator.stream(ctx, payload):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    started = time.perf_counter()
    res = await orchestrator.complete(ctx, payload)
    wall_ms = (time.perf_counter() - started) * 1000
    if res.status == 503:
        return _shed_response(res)
    headers = {
        "x-reflex-target": res.request_event.final_target or "",
        "x-reflex-attempts": str(res.request_event.attempts),
        "x-reflex-policy-version": str(res.request_event.policy_version),
        "x-reflex-request-id": res.request_event.request_id,
        "x-reflex-quality": "pass"
        if (res.request_event.quality and res.request_event.quality.pass_)
        else "fail",
    }
    if not res.request_event.hedged:  # hedge chạy song song → không trừ tuần tự được
        overhead = gateway_overhead_ms(wall_ms, [a.latency_ms for a in res.attempt_events])
        headers["x-reflex-overhead-ms"] = f"{overhead:.2f}"
    return JSONResponse(content=res.body, headers=headers)


def gateway_overhead_ms(wall_ms: float, upstream_ms: list[float]) -> float:
    """Thời gian gateway tự tốn (routing, validator, telemetry enqueue, backoff) ngoài upstream."""
    return max(0.0, wall_ms - sum(upstream_ms))


def _shed_response(res: OrchestratorResult) -> JSONResponse:
    return JSONResponse(
        status_code=res.status,
        content=res.body,
        headers={
            "Retry-After": str(res.retry_after_s or 5),
            "x-reflex-request-id": res.request_event.request_id,
            "x-reflex-policy-version": str(res.request_event.policy_version),
        },
    )


@router.get("/v1/models")
async def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {"id": "order.extract", "object": "model", "owned_by": "reflex"},
            {"id": "chat.reply", "object": "model", "owned_by": "reflex"},
            {"id": "support.triage", "object": "model", "owned_by": "reflex"},
            {"id": "cortex.reason", "object": "model", "owned_by": "reflex"},
        ],
    }
