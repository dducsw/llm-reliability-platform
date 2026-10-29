"""chaos-proxy: route trong `llm_real_routes` → vendor thật (có fault); route khác → mock."""

import json

import httpx
from fastapi.testclient import TestClient
from reflex_sim.chaos_proxy.faults import Fault, FaultSelector, FaultType
from reflex_sim.chaos_proxy.runs_watcher import ChaosRunsWatcher
from reflex_sim.chaos_proxy.server import RealUpstream, create_app
from reflex_sim.settings import Settings

REAL = {
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "real"}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
}


def _client(faults: list[Fault] | None = None) -> tuple[TestClient, list[dict]]:
    calls: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(
            {
                "url": str(req.url),
                "auth": req.headers.get("authorization"),
                "body": json.loads(req.content),
            }
        )
        return httpx.Response(200, json=REAL)

    settings = Settings(llm_api_key="sk-test", llm_base_url="https://llm.example")
    watcher = ChaosRunsWatcher()
    watcher.set_faults(faults or [])
    upstream = RealUpstream(settings, httpx.MockTransport(handler))
    return TestClient(create_app(watcher, upstream)), calls


def _post(client: TestClient, route: str) -> httpx.Response:
    return client.post(
        "/vendorA/chat/completions",
        json={"model": "ignored", "messages": [{"role": "user", "content": "hi"}]},
        headers={"x-reflex-route": route},
    )


def test_real_route_forwards_with_configured_model_and_key() -> None:
    client, calls = _client()
    resp = _post(client, "cortex.reason")
    assert resp.status_code == 200
    assert resp.headers["x-chaos-upstream"] == "real"
    assert resp.json()["choices"][0]["message"]["content"] == "real"
    assert calls[0]["url"] == "https://llm.example/chat/completions"
    assert calls[0]["auth"] == "Bearer sk-test"
    assert calls[0]["body"]["model"] == "deepseek-flash"


def test_other_routes_stay_on_mock() -> None:
    client, calls = _client()
    resp = _post(client, "chat.reply")
    assert resp.status_code == 200
    assert "x-chaos-upstream" not in resp.headers
    assert calls == []


def test_error_fault_short_circuits_before_real_call() -> None:
    fault = Fault(
        type=FaultType.ERROR, selector=FaultSelector(target="vendorA"), params={"status": 503}
    )
    client, calls = _client([fault])
    resp = _post(client, "cortex.reason")
    assert resp.status_code == 503
    assert calls == []


def test_without_key_real_route_uses_mock() -> None:
    upstream = RealUpstream(Settings(llm_api_key=""))
    assert not upstream.handles("cortex.reason")
