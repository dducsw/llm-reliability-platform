"""SDK / HTTP gọi vào gateway (stream & non-stream)."""

import httpx
import pytest
from reflex_core.policy import Candidate, CandidateRole, Policy
from reflex_gateway.main import create_app
from reflex_gateway.settings import Settings


@pytest.mark.asyncio
async def test_gateway_health_and_models() -> None:
    settings = Settings(mongodb_uri="")
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        res = await client.get("/healthz")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

        res = await client.get("/readyz")
        assert res.status_code == 200
        assert res.json() == {"status": "ready"}

        res = await client.get("/v1/models")
        assert res.status_code == 200
        data = res.json()
        assert data["object"] == "list"
        assert any(m["id"] == "order.extract" for m in data["data"])


@pytest.mark.asyncio
async def test_gateway_chat_completions_non_stream() -> None:
    settings = Settings(mongodb_uri="")
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        # Thiết lập policy trỏ tới mock:large trong test
        mock_policy = Policy(
            _id="order.extract",
            version=1,
            candidates=[Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY)],
            validators=["not_empty", "json_schema:order_v2", "no_truncation"],
        )
        app.state.policy_store._policies["order.extract"] = mock_policy

        payload = {
            "model": "order.extract",
            "messages": [{"role": "user", "content": "Cho tôi 2 ly trà sữa giao qua 123 Lê Lợi"}],
        }
        headers = {
            "x-reflex-route": "order.extract",
            "x-priority": "1",
        }
        res = await client.post("/v1/chat/completions", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.headers["x-reflex-target"] == "mock:large"
        assert res.headers["x-reflex-quality"] == "pass"
        assert "x-reflex-request-id" in res.headers
        assert res.headers["x-reflex-policy-version"] == "1"

        data = res.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        content = data["choices"][0]["message"]["content"]
        assert "items" in content  # order_v2 json format


@pytest.mark.asyncio
async def test_gateway_chat_completions_stream() -> None:
    settings = Settings(mongodb_uri="")
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        mock_policy = Policy(
            _id="chat.reply",
            version=1,
            candidates=[Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY)],
            validators=["not_empty", "no_truncation"],
        )
        app.state.policy_store._policies["chat.reply"] = mock_policy

        payload = {
            "model": "chat.reply",
            "messages": [{"role": "user", "content": "Xin chào ShopMate"}],
            "stream": True,
        }
        headers = {"x-reflex-route": "chat.reply"}
        res = await client.post("/v1/chat/completions", json=payload, headers=headers)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body = res.text
        assert "data:" in body
        assert "[DONE]" in body
