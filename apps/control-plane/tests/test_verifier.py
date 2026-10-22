import pytest
from reflex_core.actions import (
    Action,
    ActionType,
    ProposedBy,
    Verdict,
)
from reflex_cp.verifier.failback import FailbackOrchestrator
from reflex_cp.verifier.proof import RecoveryVerifier


@pytest.mark.asyncio
async def test_verifier_proof_pass() -> None:
    verifier = RecoveryVerifier(db=None)
    action = Action(
        type=ActionType.SHIFT_WEIGHT,
        params={
            "route": "order.extract",
            "from": "vendorA:large",
            "to": "vendorB:fallback",
            "pct": 1.0,
        },
        proposed_by=ProposedBy(actor="cortex"),
    )

    # 199/200 thành công sau action -> Khôi phục hoàn toàn
    result = await verifier.verify(
        action,
        baseline_good=195,
        baseline_n=200,
        after_good=199,
        after_n=200,
    )

    assert result.verdict == Verdict.PASS
    assert result.after_ci[0] >= 0.95
    assert action.verification is not None


@pytest.mark.asyncio
async def test_failback_steps() -> None:
    orch = FailbackOrchestrator(db=None)
    parent_act = Action(
        type=ActionType.SHIFT_WEIGHT,
        params={
            "route": "order.extract",
            "from": "vendorA:large",
            "to": "vendorB:fallback",
            "pct": 1.0,
        },
        proposed_by=ProposedBy(actor="cortex"),
    )

    step1 = await orch.advance(parent_act, current_pct=0)
    assert step1 is not None
    assert step1.type == ActionType.FAILBACK_STEP
    assert step1.params["pct"] == 10

    step2 = await orch.advance(parent_act, current_pct=10)
    assert step2 is not None
    assert step2.params["pct"] == 50

    step3 = await orch.advance(parent_act, current_pct=50)
    assert step3 is not None
    assert step3.params["pct"] == 100

    step4 = await orch.advance(parent_act, current_pct=100)
    assert step4 is None
