import pytest
from httpx import ASGITransport, AsyncClient
from reflex_cp.main import create_app
from reflex_cp.settings import Settings


@pytest.mark.asyncio
async def test_webhook_unauthorized() -> None:
    settings = Settings(reflex_webhook_token="secret_token_123")
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/hooks/datadog",
            json={
                "monitor_id": 111,
                "alert_transition": "Triggered",
                "title": "Alert",
            },
            headers={"X-Reflex-Webhook-Token": "wrong_token"},
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_webhook_success() -> None:
    settings = Settings(reflex_webhook_token="secret_token_123")
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/hooks/datadog",
            json={
                "monitor_id": 111,
                "alert_transition": "Triggered",
                "title": "Alert",
                "tags": ["target:vendorA:large", "route:order.extract"],
                "diagnosis": "output truncation",
            },
            headers={"X-Reflex-Webhook-Token": "secret_token_123"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        assert data.get("incident_key") is not None
