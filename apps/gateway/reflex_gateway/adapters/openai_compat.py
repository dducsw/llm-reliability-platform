"""Adapter `openai_compat` — chuẩn hóa usage, finish_reason, lỗi."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

import httpx
from reflex_gateway.adapters.base import UpstreamResult


class OpenaiCompatAdapter:
    name = "openai_compat"

    async def complete(self, target: dict, payload: dict, timeout_s: float) -> UpstreamResult:
        base_url = target.get("base_url") or target.get("base_url_ref", "http://localhost:8070/v1")
        if not base_url.endswith("/chat/completions"):
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            url = base_url

        headers = {"Content-Type": "application/json"}
        api_key = target.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                latency_ms = (time.perf_counter() - start) * 1000.0
                status = resp.status_code
                if status >= 400:
                    return UpstreamResult(
                        status=status,
                        content="",
                        finish_reason="error",
                        tokens_in=0,
                        tokens_out=0,
                        latency_ms=latency_ms,
                        ttft_ms=latency_ms,
                        raw={"error": resp.text},
                        error_class="http_error",
                    )
                data = resp.json()
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")
                usage = data.get("usage", {})
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)

                return UpstreamResult(
                    status=200,
                    content=content,
                    finish_reason=finish_reason,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    ttft_ms=latency_ms * 0.4,
                    raw=data,
                )
            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start) * 1000.0
                return UpstreamResult(
                    status=504,
                    content="",
                    finish_reason="timeout",
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=latency_ms,
                    ttft_ms=None,
                    raw={"error": "timeout"},
                    error_class="timeout",
                )
            except Exception as e:
                latency_ms = (time.perf_counter() - start) * 1000.0
                return UpstreamResult(
                    status=502,
                    content="",
                    finish_reason="error",
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=latency_ms,
                    ttft_ms=None,
                    raw={"error": str(e)},
                    error_class="network_error",
                )

    async def stream(self, target: dict, payload: dict, timeout_s: float) -> AsyncIterator[dict]:
        res = await self.complete(target, payload, timeout_s)
        yield {
            "choices": [
                {"delta": {"role": "assistant", "content": res.content}, "finish_reason": None}
            ]
        }
        yield {
            "choices": [{"delta": {}, "finish_reason": res.finish_reason}],
            "usage": {
                "prompt_tokens": res.tokens_in,
                "completion_tokens": res.tokens_out,
                "total_tokens": res.tokens_in + res.tokens_out,
            },
        }
