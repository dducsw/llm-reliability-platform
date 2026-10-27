import json

import httpx
import pytest
from reflex_gateway.adapters.anthropic import AnthropicAdapter, to_anthropic_payload
from reflex_gateway.adapters.mock import MockAdapter

TARGET = {
    "_id": "anthropic:haiku",
    "model": "claude-haiku",
    "api_key": "k",
    "base_url": "http://up/v1",
}
PAYLOAD = {
    "messages": [{"role": "system", "content": "be terse"}, {"role": "user", "content": "hi"}],
    "max_tokens": 64,
}


def test_to_anthropic_payload_lifts_system_message() -> None:
    body = to_anthropic_payload(TARGET, PAYLOAD)
    assert body["system"] == "be terse"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["model"] == "claude-haiku"


@pytest.mark.asyncio
async def test_anthropic_normalizes_usage_and_finish_reason() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "msg_1",
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "max_tokens",
                "usage": {"input_tokens": 7, "output_tokens": 3},
            },
        )

    res = await AnthropicAdapter(httpx.MockTransport(handler)).complete(TARGET, PAYLOAD, 1.0)
    assert seen["url"] == "http://up/v1/messages"
    assert (res.status, res.content, res.finish_reason) == (200, "hello", "length")
    assert (res.tokens_in, res.tokens_out) == (7, 3)
    assert res.raw["usage"]["total_tokens"] == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "error_class"), [(429, "rate_limited"), (500, "http_error")])
async def test_anthropic_maps_http_errors(status: int, error_class: str) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status, text="boom"))
    res = await AnthropicAdapter(transport).complete(TARGET, PAYLOAD, 1.0)
    assert (res.status, res.error_class) == (status, error_class)


@pytest.mark.asyncio
async def test_anthropic_timeout_is_504() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    res = await AnthropicAdapter(httpx.MockTransport(handler)).complete(TARGET, PAYLOAD, 1.0)
    assert (res.status, res.error_class) == (504, "timeout")


@pytest.mark.asyncio
async def test_mock_adapter_is_deterministic_for_same_seed() -> None:
    payload = {
        "model": "chat.reply",
        "seed": 7,
        "messages": [{"role": "user", "content": "xin chào"}],
    }
    a = await MockAdapter().complete({"route": "chat.reply"}, payload, 1.0)
    b = await MockAdapter().complete({"route": "chat.reply"}, payload, 1.0)
    assert a.content == b.content and a.status == 200


def test_resolve_refs_builds_base_url_and_model(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from reflex_gateway.target_catalog import resolve_refs

    monkeypatch.setenv("CHAOS_PROXY_URL", "http://chaos:8070/")
    monkeypatch.setenv("VENDOR_A_LARGE_MODEL", "gpt-x")
    doc = resolve_refs(
        {
            "_id": "vendorA:large",
            "vendor": "vendorA",
            "base_url_ref": "CHAOS_PROXY_URL/vendorA",
            "model_ref": {"env_var": "VENDOR_A_LARGE_MODEL"},
        }
    )
    assert doc["base_url"] == "http://chaos:8070/vendorA"
    assert doc["model"] == "gpt-x"


async def test_openai_compat_forwards_route_header(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """chaos-proxy/mock-llm chọn output + fault theo `x-reflex-route`."""
    from reflex_gateway.adapters import openai_compat

    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(req.headers)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}], "usage": {}})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        openai_compat.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    target = {"base_url": "http://chaos:8070/vendorA", "route": "order.extract"}
    res = await openai_compat.OpenaiCompatAdapter().complete(target, PAYLOAD, 1.0)
    assert res.status == 200
    assert seen["x-reflex-route"] == "order.extract"
