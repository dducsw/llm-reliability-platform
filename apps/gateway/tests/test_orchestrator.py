import pytest
from reflex_core.policy import Candidate, CandidateRole, Policy
from reflex_gateway.engine.orchestrator import Orchestrator, RequestContext
from reflex_gateway.policy_store import PolicyStore
from reflex_gateway.target_catalog import TargetCatalog
from reflex_gateway.telemetry.queue import TelemetryQueue


@pytest.mark.asyncio
async def test_orchestrator_complete_mock() -> None:
    ps = PolicyStore(db=None)
    policy = Policy(
        _id="order.extract",
        version=1,
        candidates=[
            Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY),
        ],
    )
    ps.set(policy)

    tc = TargetCatalog(db=None)
    tq = TelemetryQueue(maxsize=100)
    orch = Orchestrator(
        policy_store=ps,
        target_catalog=tc,
        telemetry_queue=tq,
        gateway_id="gw-test",
    )

    ctx = RequestContext(
        request_id="req-123",
        route="order.extract",
        priority=1,
        session="sess-1",
        deadline_ms=5000,
    )

    result = await orch.complete(ctx, {"messages": [{"role": "user", "content": "Extract order"}]})
    assert result.request_event.request_id == "req-123"
    assert result.request_event.outcome.value == "ok"
    assert len(result.attempt_events) == 1
    assert result.attempt_events[0].kind.value == "primary"
    assert tq.qsize() == 2  # 1 attempt + 1 request


@pytest.mark.asyncio
async def test_orchestrator_retries_after_quality_fail() -> None:
    from reflex_gateway.adapters import registry
    from reflex_gateway.adapters.base import UpstreamResult

    class _Flaky:
        name = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, target: dict, payload: dict, timeout_s: float) -> UpstreamResult:
            self.calls += 1
            content = "" if self.calls == 1 else "ok"
            return UpstreamResult(
                status=200,
                content=content,
                finish_reason="stop",
                tokens_in=1,
                tokens_out=1,
                latency_ms=1.0,
                ttft_ms=1.0,
                raw={"choices": [{"message": {"content": content}}]},
            )

        def stream(self, target: dict, payload: dict, timeout_s: float):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    flaky = _Flaky()
    registry._ADAPTERS["flaky"] = flaky  # type: ignore[assignment]
    try:
        ps = PolicyStore(db=None)
        ps.set(
            Policy(
                _id="chat.reply",
                version=1,
                validators=["not_empty"],
                candidates=[Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY)],
            )
        )
        tc = TargetCatalog(db=None)
        tc._targets["mock:large"] = {"_id": "mock:large", "adapter": "flaky"}
        orch = Orchestrator(policy_store=ps, target_catalog=tc, telemetry_queue=TelemetryQueue(100))
        ctx = RequestContext(
            request_id="r", route="chat.reply", priority=1, session=None, deadline_ms=5000
        )
        res = await orch.complete(ctx, {"messages": [{"role": "user", "content": "hi"}]})
    finally:
        registry._ADAPTERS.pop("flaky", None)

    assert [a.kind.value for a in res.attempt_events] == ["primary", "quality_retry"]
    assert res.request_event.outcome.value == "ok"
