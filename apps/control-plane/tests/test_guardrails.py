import pytest
from reflex_core.actions import (
    Action,
    ActionState,
    ActionType,
    PageHumanParams,
    ProposedBy,
    ShiftWeightParams,
)
from reflex_cp.policy_engine.decision import decide
from reflex_cp.policy_engine.guardrails import evaluate_all


@pytest.mark.asyncio
async def test_guardrails_pass_auto() -> None:
    action = Action(
        type=ActionType.SHIFT_WEIGHT,
        params=ShiftWeightParams(
            route="order.extract",
            **{"from": "vendorA:large"},
            to="vendorB:fallback",
            pct=1.0,
        ).model_dump(by_alias=True),
        proposed_by=ProposedBy(actor="cortex"),
    )
    guardrails = await evaluate_all(action, db=None)
    assert all(g.pass_ for g in guardrails)

    decision = await decide(action, db=None)
    assert decision.mode == "auto"
    assert action.state == ActionState.APPROVED


@pytest.mark.asyncio
async def test_guardrail_human_only_requires_human() -> None:
    action = Action(
        type=ActionType.PAGE_HUMAN,
        params=PageHumanParams(reason="Manual intervention needed").model_dump(),
        proposed_by=ProposedBy(actor="cortex"),
    )
    guardrails = await evaluate_all(action, db=None)
    human_g = next(g for g in guardrails if g.name == "human_only")
    assert human_g.pass_ is False

    decision = await decide(action, db=None)
    assert decision.mode == "human"
    assert action.state == ActionState.AWAITING_APPROVAL
