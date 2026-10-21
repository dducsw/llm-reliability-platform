"""Payload webhook Datadog khớp reflex_cp.hooks.payload."""

from reflex_cp.hooks.payload import DatadogWebhookPayload


def test_datadog_webhook_payload_valid() -> None:
    raw = {
        "monitor_id": 987654,
        "alert_id": "alert-12345",
        "alert_transition": "Triggered",
        "title": "[Triggered] High provider burn rate on vendorA:large",
        "tags": ["target:vendorA:large", "route:order.extract", "slo:provider_quality"],
        "diagnosis": "server-side output truncation",
        "date": 1729500000,
    }
    payload = DatadogWebhookPayload.model_validate(raw)
    assert payload.monitor_id == 987654
    assert payload.alert_id == "alert-12345"
    assert payload.alert_transition == "Triggered"
    assert "target:vendorA:large" in payload.tags
    assert payload.diagnosis == "server-side output truncation"
