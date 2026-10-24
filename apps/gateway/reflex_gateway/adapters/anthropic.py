"""Adapter `anthropic` — chuẩn hóa usage, finish_reason, lỗi."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from reflex_gateway.adapters.base import UpstreamResult

_STOP_REASONS = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}
_DEFAULT_BASE_URL = "https://api.anthropic.com/v1"


def to_anthropic_payload(target: dict, payload: dict) -> dict:
    system = [m["content"] for m in payload.get("messages", []) if m.get("role") == "system"]
    messages = [m for m in payload.get("messages", []) if m.get("role") != "system"]
    body: dict = {
        "model": target.get("model", payload.get("model", "")),
        "max_tokens": payload.get("max_tokens", 1024),
        "messages": messages,
    }
    if system:
        body["system"] = "\n".join(system)
    if "temperature" in payload:
        body["temperature"] = payload["temperature"]
    return body


class AnthropicAdapter:
    name = "anthropic"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def complete(self, target: dict, payload: dict, timeout_s: float) -> UpstreamResult:
        url = f"{(target.get('base_url') or _DEFAULT_BASE_URL).rstrip('/')}/messages"
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": target.get("api_key", ""),
        }
        start = time.perf_counter()

        def elapsed() -> float:
            return (time.perf_counter() - start) * 1000.0

        try:
            async with httpx.AsyncClient(timeout=timeout_s, transport=self._transport) as client:
                resp = await client.post(
                    url, json=to_anthropic_payload(target, payload), headers=headers
                )
        except httpx.TimeoutException:
            return _error(504, "timeout", elapsed(), "timeout")
        except httpx.HTTPError as e:
            return _error(502, "connect_error", elapsed(), str(e))

        latency_ms = elapsed()
        if resp.status_code >= 400:
            error_class = "rate_limited" if resp.status_code == 429 else "http_error"
            return _error(resp.status_code, error_class, latency_ms, resp.text)

        data = resp.json()
        content = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        usage = data.get("usage", {})
        tokens_in, tokens_out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        finish_reason = _STOP_REASONS.get(data.get("stop_reason") or "", "stop")
        return UpstreamResult(
            status=200,
            content=content,
            finish_reason=finish_reason,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            ttft_ms=None,
            raw={
                "id": data.get("id", ""),
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": finish_reason,
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
        yield {
            "choices": [
                {"delta": {"role": "assistant", "content": res.content}, "finish_reason": None}
            ]
        }
        yield {"choices": [{"delta": {}, "finish_reason": res.finish_reason}]}


def _error(status: int, error_class: str, latency_ms: float, detail: str) -> UpstreamResult:
    return UpstreamResult(
        status=status,
        content="",
        finish_reason="error",
        tokens_in=0,
        tokens_out=0,
        latency_ms=latency_ms,
        ttft_ms=None,
        raw={"error": detail},
        error_class=error_class,
    )
