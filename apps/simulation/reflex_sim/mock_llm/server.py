from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from reflex_sim.mock_llm import outputs, profiles


def _seed_for(request: Request, payload: dict) -> int:
    """Deterministic theo request_id (hoặc `seed` trong payload) — cùng input, cùng output."""
    if "seed" in payload:
        return int(payload["seed"])
    key = request.headers.get("x-reflex-request-id") or json.dumps(
        payload.get("messages", []), sort_keys=True
    )
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")


def _split_chunks(content: str, size: int = 24) -> list[str]:
    return [content[i : i + size] for i in range(0, len(content), size)] or [""]


def create_app(latency_scale: float | None = None) -> FastAPI:
    """POST /v1/chat/completions (OpenAI-compatible), stream & non-stream."""
    scale = (
        float(os.getenv("MOCK_LATENCY_SCALE", "1.0")) if latency_scale is None else latency_scale
    )
    app = FastAPI(title="Reflex Mock LLM")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/v1/chat/completions")
    @app.post("/chat/completions")
    async def chat_completions(request: Request) -> Response:
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                {"error": {"type": "invalid_request_error", "message": "invalid JSON"}}, 400
            )

        messages = payload.get("messages", [])
        route = request.headers.get("x-reflex-route") or payload.get("model", "chat.reply")
        rng = random.Random(_seed_for(request, payload))
        profile = profiles.get_profile(request.headers.get("x-mock-profile", "mock"))

        content = outputs.generate(route, messages, rng)
        tokens_in = max(1, sum(len(str(m.get("content", ""))) // 4 for m in messages))
        tokens_out = max(1, len(content) // 4)
        ttft_s = rng.lognormvariate(profile.ttft_mu, profile.ttft_sigma) / 1000.0 * scale
        tps = max(1.0, rng.gauss(profile.tps_mean, profile.tps_std))
        usage = {
            "prompt_tokens": tokens_in,
            "completion_tokens": tokens_out,
            "total_tokens": tokens_in + tokens_out,
        }

        if not payload.get("stream"):
            await asyncio.sleep(ttft_s + tokens_out / tps * scale)
            return JSONResponse(
                {
                    "id": f"mock-{rng.getrandbits(32):08x}",
                    "object": "chat.completion",
                    "model": payload.get("model", route),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": usage,
                }
            )

        async def sse() -> AsyncIterator[str]:
            await asyncio.sleep(ttft_s)
            chunks = _split_chunks(content)
            for i, piece in enumerate(chunks):
                delta = {"role": "assistant", "content": piece} if i == 0 else {"content": piece}
                yield f"data: {json.dumps({'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]})}\n\n"
                await asyncio.sleep(len(piece) / 4 / tps * scale)
            final = {
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": usage,
            }
            yield f"data: {json.dumps(final)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    return app
