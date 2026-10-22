from reflex_telemetry.datadog_api import strip_chaos_fields
from reflex_telemetry.tags import base_tags


def test_base_tags_only_includes_given_dimensions() -> None:
    assert base_tags("ci") == ["env:ci"]
    assert base_tags("ci", route="order.extract", target="mock:large") == [
        "env:ci",
        "route:order.extract",
        "target:mock:large",
    ]


def test_strip_chaos_fields_removes_nested_keys_and_tags() -> None:
    payload = {
        "attributes": {
            "chaos.fault": "truncate",
            "status": "error",
            "tags": ["chaos.fault:x", "env:ci"],
        },
        "items": [{"chaos_run": "r1", "id": 1}],
    }
    assert strip_chaos_fields(payload) == {
        "attributes": {"status": "error", "tags": ["env:ci"]},
        "items": [{"id": 1}],
    }


import json
from datetime import UTC, datetime

import httpx
import pytest
from reflex_telemetry.datadog_api import DatadogApi, DatadogApiError

T0, T1 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC), datetime(2026, 10, 22, 9, 5, tzinfo=UTC)


def _api(handler) -> DatadogApi:  # type: ignore[no-untyped-def]
    return DatadogApi("ak", "pk", "datadoghq.com", transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_logs_sends_keys_and_strips_chaos() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"data": [{"attributes": {"message": "x", "chaos.fault": "truncate"}}]}
        )

    logs = await _api(handler).search_logs("service:reflex-gateway", T0, T1, limit=5)
    assert seen["headers"]["dd-api-key"] == "ak" and seen["headers"]["dd-application-key"] == "pk"
    assert seen["body"]["page"]["limit"] == 5
    assert logs == [{"attributes": {"message": "x"}}]


@pytest.mark.asyncio
async def test_send_event_and_error_mapping() -> None:
    sent: list[dict] = []

    def ok(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(202, json={"status": "ok"})

    await _api(ok).send_event("t", "body", ["env:ci"], alert_type="warning")
    assert sent == [{"title": "t", "text": "body", "tags": ["env:ci"], "alert_type": "warning"}]

    with pytest.raises(DatadogApiError):
        await _api(lambda _: httpx.Response(403, text="forbidden")).get_monitor(1)
