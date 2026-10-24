"""FastAPI Chaos Proxy server: nhận request, inject faults, gắn x-chaos-fault."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from reflex_sim.chaos_proxy import injector
from reflex_sim.chaos_proxy.runs_watcher import ChaosRunsWatcher
from reflex_sim.mock_llm import outputs


def create_app(watcher: ChaosRunsWatcher | None = None) -> FastAPI:
    app = FastAPI(title="Reflex Chaos Proxy")
    proxy_watcher = watcher or ChaosRunsWatcher()
    app.state.watcher = proxy_watcher

    @app.post("/{vendor}/chat/completions")
    @app.post("/{vendor}/v1/chat/completions")
    async def chat_completions(vendor: str, request: Request) -> Response:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        route = request.headers.get("x-reflex-route") or payload.get("model", "chat.reply")
        rng = random.Random(payload.get("seed", int(time.time() * 1000) % 100000))

        # Khởi tạo response mẫu
        messages = payload.get("messages", [])
        content = outputs.generate(route, messages, rng)
        tokens_in = max(1, sum(len(str(m.get("content", ""))) // 4 for m in messages))
        tokens_out = max(1, len(content) // 4)

        base_res: dict[str, Any] = {
            "id": f"chaos-resp-{vendor}",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": tokens_in,
                "completion_tokens": tokens_out,
                "total_tokens": tokens_in + tokens_out,
            },
        }

        # Tìm faults áp dụng
        active_faults = proxy_watcher.active_faults
        matched_faults = injector.select(active_faults, target=vendor, route=route, rng=rng)

        headers: dict[str, str] = {}
        final_res = base_res

        for fault in matched_faults:
            headers["x-chaos-fault"] = fault.type.value

            # Độ trễ bổ sung
            if "add_ms" in fault.params:
                delay_s = float(fault.params["add_ms"]) / 1000.0
                await asyncio.sleep(delay_s)

            final_res = injector.apply(fault, final_res, rng)
            if "status_code" in final_res:
                status = int(final_res["status_code"])
                if "retry_after" in final_res:
                    headers["Retry-After"] = str(final_res["retry_after"])
                return JSONResponse(
                    content=final_res.get("error", {}), status_code=status, headers=headers
                )

        return JSONResponse(content=final_res, headers=headers)

    return app
