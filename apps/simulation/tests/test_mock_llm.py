import json
import random

from reflex_sim.mock_llm import outputs, profiles


def test_outputs_order_extract_valid_json() -> None:
    rng = random.Random(42)
    out = outputs.generate("order.extract", [], rng)
    data = json.loads(out)
    assert "items" in data
    assert "address" in data
    assert len(data["items"]) > 0


def test_outputs_chat_reply() -> None:
    rng = random.Random(42)
    out = outputs.generate("chat.reply", [], rng)
    assert isinstance(out, str)
    assert len(out) > 5


def test_profiles() -> None:
    prof = profiles.get_profile("large")
    assert prof.ttft_mu > 0
    assert prof.tps_mean > 0


def _client():  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient
    from reflex_sim.mock_llm.server import create_app

    return TestClient(create_app(latency_scale=0.0))


BODY = {"messages": [{"role": "user", "content": "Giao 2 áo size M"}]}


def test_server_is_deterministic_per_request_id() -> None:
    client = _client()
    hdr = {"x-reflex-route": "order.extract", "x-reflex-request-id": "req-1"}
    a = client.post("/v1/chat/completions", json=BODY, headers=hdr).json()
    b = client.post("/v1/chat/completions", json=BODY, headers=hdr).json()
    assert a["choices"] == b["choices"]
    assert json.loads(a["choices"][0]["message"]["content"])["items"]
    assert (
        a["usage"]["total_tokens"] == a["usage"]["prompt_tokens"] + a["usage"]["completion_tokens"]
    )


def test_server_streams_sse_that_reassembles_to_content() -> None:
    client = _client()
    hdr = {"x-reflex-route": "chat.reply", "x-reflex-request-id": "req-2"}
    full = client.post("/v1/chat/completions", json=BODY, headers=hdr).json()["choices"][0][
        "message"
    ]["content"]
    resp = client.post("/v1/chat/completions", json={**BODY, "stream": True}, headers=hdr)
    events = [line[6:] for line in resp.text.splitlines() if line.startswith("data: ")]
    assert events[-1] == "[DONE]"
    chunks = [json.loads(e) for e in events[:-1]]
    assert "".join(c["choices"][0]["delta"].get("content", "") for c in chunks) == full
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_server_rejects_invalid_json() -> None:
    assert _client().post("/v1/chat/completions", content=b"{nope").status_code == 400
