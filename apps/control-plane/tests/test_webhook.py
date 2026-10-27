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


@pytest.mark.asyncio
async def test_webhook_datadog_template_shape() -> None:
    """Body đúng như template webhooks.tf render: $TAGS là chuỗi, có alert_id/date."""
    settings = Settings(reflex_webhook_token="secret_token_123")
    app = create_app(settings)
    transport = ASGITransport(app=app)
    body = {
        "monitor_id": 222,
        "alert_id": "7319",
        "alert_transition": "Triggered",
        "title": "[Triggered] M1 quality burn",
        "tags": "env:demo,target:vendorA:large,route:order.extract,sli:quality",
        "diagnosis": "burn rate 14.4x",
        "date": 1793000000000,
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/hooks/datadog", json=body, headers={"X-Reflex-Webhook-Token": "secret_token_123"}
        )
        assert res.status_code == 200
        assert res.json()["incident_key"] is not None

        res = await client.post(
            "/hooks/datadog",
            json={**body, "alert_transition": "Recovered"},
            headers={"X-Reflex-Webhook-Token": "secret_token_123"},
        )
        assert res.status_code == 200
        assert res.json()["incident_key"] is None
