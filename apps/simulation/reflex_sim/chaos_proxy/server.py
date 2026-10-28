"""FastAPI Chaos Proxy server: nhận request, inject faults, gắn x-chaos-fault."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from reflex_sim.chaos_proxy import injector
from reflex_sim.chaos_proxy.faults import Fault, FaultType
from reflex_sim.chaos_proxy.runs_watcher import ChaosRunsWatcher
from reflex_sim.mock_llm import outputs
from reflex_sim.settings import Settings

# Fault trả lỗi ngay → không cần (và không nên) gọi vendor thật
_SHORT_CIRCUIT = {FaultType.ERROR, FaultType.RATE_LIMIT}


class RealUpstream:
    """Forward route được chọn tới vendor OpenAI-compatible thật; key chỉ nằm ở chaos-proxy."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.routes = {r.strip() for r in settings.llm_real_routes.split(",") if r.strip()}
        self._settings = settings
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def handles(self, route: str) -> bool:
        return bool(self._settings.llm_api_key) and route in self.routes

    async def complete(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if self._client is None:
            self._client = httpx.AsyncClient(transport=self._transport)
        s = self._settings
        body = {**payload, "model": s.llm_model}
        resp = await self._client.post(
            f"{s.llm_base_url.rstrip('/')}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {s.llm_api_key}"},
            timeout=s.llm_timeout_s,
        )
        try:
            data = resp.json()
        except ValueError:
            data = {"error": {"message": resp.text[:500]}}
        return resp.status_code, data

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def create_app(
    watcher: ChaosRunsWatcher | None = None, upstream: RealUpstream | None = None
) -> FastAPI:
    real = upstream or RealUpstream(Settings())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await real.aclose()

    app = FastAPI(title="Reflex Chaos Proxy", lifespan=lifespan)
    proxy_watcher = watcher or ChaosRunsWatcher()
    app.state.watcher = proxy_watcher
    app.state.upstream = real

    @app.post("/{vendor}/chat/completions")
    @app.post("/{vendor}/v1/chat/completions")
    async def chat_completions(vendor: str, request: Request) -> Response:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        route = request.headers.get("x-reflex-route") or payload.get("model", "chat.reply")
        rng = random.Random(payload.get("seed", int(time.time() * 1000) % 100000))

        # Tìm faults áp dụng
        active_faults = proxy_watcher.active_faults
        matched_faults = injector.select(active_faults, target=vendor, route=route, rng=rng)
        headers: dict[str, str] = {}

        if real.handles(route) and not any(f.type in _SHORT_CIRCUIT for f in matched_faults):
            headers["x-chaos-upstream"] = "real"
            try:
                status, data = await real.complete(payload)
            except httpx.TimeoutException:
                return JSONResponse({"error": {"message": "upstream timeout"}}, 504, headers)
            except httpx.HTTPError as e:
                return JSONResponse({"error": {"message": f"upstream: {e}"}}, 502, headers)
            if status >= 400:
                return JSONResponse(data, status, headers)
            return await _apply_faults(matched_faults, data, rng, headers)

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

        return await _apply_faults(matched_faults, base_res, rng, headers)

    return app


async def _apply_faults(
    faults: list[Fault], res: dict[str, Any], rng: random.Random, headers: dict[str, str]
) -> Response:
    final_res = res
    for fault in faults:
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
