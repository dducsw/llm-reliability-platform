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


@pytest.mark.asyncio
async def test_find_monitors_filters_by_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["name"] == "M3_quality"
        return httpx.Response(
            200,
            json=[
                {"name": "[reflex] M3_quality_fast_burn", "overall_state": "Alert"},
                {"name": "M30_other", "overall_state": "OK"},
            ],
        )

    found = await _api(handler).find_monitors("M3_quality")
    assert [m["overall_state"] for m in found] == ["Alert"]
