"""SE-7.4 — investigation phát ra cây span LLMObs agent → task/workflow → tool → llm."""

import json
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from reflex_cortex import agent as agent_mod
from reflex_cortex.agent import CortexAgent, GatewayLlm
from reflex_cortex.settings import Settings


class _Recorder:
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.spans: list[tuple[str, str, str | None]] = []  # (kind, name, parent)
        self.annotations: dict[str, dict[str, Any]] = {}

    @contextmanager
    def span(self, kind: str, name: str, **_: Any):  # type: ignore[no-untyped-def]
        self.spans.append((kind, name, self.stack[-1] if self.stack else None))
        self.stack.append(name)
        try:
            yield name
        finally:
            self.stack.pop()

    def annotate(self, s: str | None, **kw: Any) -> None:
        if s is not None:
            self.annotations.setdefault(s, {}).update(kw)


@pytest.fixture()
def rec(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    r = _Recorder()
    monkeypatch.setattr(agent_mod.llmobs, "span", r.span)
    monkeypatch.setattr(agent_mod.llmobs, "annotate", r.annotate)
    return r


def _gateway(replies: list[dict[str, Any]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-reflex-route"] == "cortex.reason"
        body = {
            "choices": [{"message": {"content": json.dumps(replies.pop(0))}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        return httpx.Response(200, json=body, headers={"x-reflex-target": "mock:primary"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_investigation_span_tree(rec: _Recorder, monkeypatch: pytest.MonkeyPatch) -> None:
    final = {
        "side": "provider",
        "hypotheses": [{"id": "H1", "statement": "s", "confidence": 0.8, "evidence": []}],
    }
    transport = _gateway([{"tool": "dd.logs_search", "args": {"query": "x"}}, {"final": final}])
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))

    settings = Settings(gateway_url="http://gw")
    llm = GatewayLlm(settings.gateway_url, settings.reason_route)
    await CortexAgent(db=None, llm=llm, settings=settings).investigate("INC-7")

    assert rec.spans[0] == ("agent", "cortex.investigate", None)
    assert ("task", "cortex.context_pack", "cortex.investigate") in rec.spans
    assert ("workflow", "cortex.reason", "cortex.investigate") in rec.spans
    assert ("tool", "dd.logs_search", "cortex.reason") in rec.spans
    assert [s for s in rec.spans if s[0] == "llm"] == [("llm", "cortex.llm", "cortex.reason")] * 2

    assert rec.annotations["cortex.investigate"]["tags"]["incident_id"] == "INC-7"
    assert rec.annotations["cortex.llm"]["metrics"]["total_tokens"] == 15
    assert rec.annotations["cortex.llm"]["tags"]["reflex.target"] == "mock:primary"
    assert rec.annotations["dd.logs_search"]["input_data"] == {"query": "x"}
