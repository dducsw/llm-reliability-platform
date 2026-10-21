"""Adapter `mock` — chuẩn hóa usage, finish_reason, lỗi."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator

from reflex_gateway.adapters.base import UpstreamResult
from reflex_sim.mock_llm import outputs


class MockAdapter:
    name = "mock"

    async def complete(self, target: dict, payload: dict, timeout_s: float) -> UpstreamResult:
        start = time.perf_counter()
        messages = payload.get("messages", [])
        route = target.get("route", payload.get("model", "chat.reply"))
        rng = random.Random(payload.get("seed", 42))

        # Giả lập latency nhỏ
        await asyncio.sleep(0.01)
        ttft = 10.0
        content = outputs.generate(route, messages, rng)
        latency = (time.perf_counter() - start) * 1000.0

        tokens_in = max(1, sum(len(str(m.get("content", ""))) // 4 for m in messages))
        tokens_out = max(1, len(content) // 4)

        return UpstreamResult(
            status=200,
            content=content,
            finish_reason="stop",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency,
            ttft_ms=ttft,
            raw={
                "id": "mock-cmpl-1",
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
            },
        )

    async def stream(self, target: dict, payload: dict, timeout_s: float) -> AsyncIterator[dict]:
        res = await self.complete(target, payload, timeout_s)
        # Yield single chunk or split chunk
        yield {
            "choices": [{"delta": {"role": "assistant", "content": res.content}, "finish_reason": None}]
        }
        yield {
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": res.tokens_in,
                "completion_tokens": res.tokens_out,
                "total_tokens": res.tokens_in + res.tokens_out,
            },
        }
