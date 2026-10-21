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
