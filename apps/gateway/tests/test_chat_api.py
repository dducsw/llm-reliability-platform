from fastapi.testclient import TestClient
from reflex_core.policy import Candidate, CandidateRole, Policy
from reflex_gateway.main import create_app
from reflex_gateway.settings import Settings


def _client() -> TestClient:
    return TestClient(create_app(Settings(mongodb_uri="")))


def _mock_only(client: TestClient, route: str) -> None:
    """Ép route chỉ dùng mock:large để test không phụ thuộc mạng/chaos-proxy."""
    client.app.state.policy_store.set(  # type: ignore[attr-defined]
        Policy(
            _id=route,
            version=1,
            candidates=[Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY)],
            validators=["not_empty"],
        )
    )


def test_chat_completions_sets_reflex_headers(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DD_TRACE_ENABLED", "false")
    with _client() as client:
        _mock_only(client, "chat.reply")
        resp = client.post(
            "/v1/chat/completions",
            headers={"x-reflex-route": "chat.reply", "x-reflex-request-id": "req-api-1"},
            json={"messages": [{"role": "user", "content": "xin chào"}]},
        )
    assert resp.status_code == 200
    assert resp.headers["x-reflex-request-id"] == "req-api-1"
    assert resp.headers["x-reflex-attempts"] == "1"
    assert float(resp.headers["x-reflex-overhead-ms"]) >= 0
    assert resp.json()["choices"][0]["message"]["content"]


def test_overhead_subtracts_upstream_time() -> None:
    from reflex_gateway.api.chat import gateway_overhead_ms

    assert gateway_overhead_ms(120.0, [100.0, 15.0]) == 5.0
    assert gateway_overhead_ms(50.0, [60.0]) == 0.0  # đồng hồ lệch → không âm


def test_missing_route_is_400(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DD_TRACE_ENABLED", "false")
    with _client() as client:
        resp = client.post("/v1/chat/completions", json={"messages": []})
    assert resp.status_code == 400


def test_stream_ends_with_done(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DD_TRACE_ENABLED", "false")
    with _client() as client:
        _mock_only(client, "chat.reply")
        resp = client.post(
            "/v1/chat/completions",
            headers={"x-reflex-route": "chat.reply"},
            json={"stream": True, "messages": [{"role": "user", "content": "hi"}]},
        )
    assert resp.text.rstrip().endswith("data: [DONE]")


def test_shed_is_503_with_retry_after_for_both_modes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DD_TRACE_ENABLED", "false")
    with _client() as client:
        _mock_only(client, "chat.reply")
        orch = client.app.state.orchestrator  # type: ignore[attr-defined]
        for _ in range(30):
            orch.state.on_attempt("mock:large", "chat.reply", ok=False, quality_ok=False)
        for stream in (False, True):
            resp = client.post(
                "/v1/chat/completions",
                headers={"x-reflex-route": "chat.reply", "x-priority": "2"},
                json={"messages": [{"role": "user", "content": "hi"}], "stream": stream},
            )
            assert resp.status_code == 503
            assert resp.headers["retry-after"] == "5"
            assert resp.json()["error"]["reflex"]["reason"] == "shed"
        ok = client.post(
            "/v1/chat/completions",
            headers={"x-reflex-route": "chat.reply", "x-priority": "0"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert ok.status_code == 200
