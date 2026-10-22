from datetime import UTC, datetime

import pytest
from reflex_core.actions import (
    Action,
    ActionState,
    ActionType,
    ProposedBy,
    ShiftWeightParams,
)
from reflex_core.policy import Candidate, CandidateRole, Policy
from reflex_cp.actuator.apply import Actuator
from reflex_cp.actuator.transforms import apply_action


def test_apply_action_shift_weight() -> None:
    policy = Policy(
        _id="order.extract",
        version=1,
        candidates=[
            Candidate(target="vendorA:large", weight=0.8, role=CandidateRole.PRIMARY),
            Candidate(target="vendorB:fallback", weight=0.2, role=CandidateRole.SECONDARY),
        ],
    )
    action = Action(
        type=ActionType.SHIFT_WEIGHT,
        params=ShiftWeightParams(
            route="order.extract",
            **{"from": "vendorA:large"},
            to="vendorB:fallback",
            pct=1.0,
        ).model_dump(by_alias=True),
        proposed_by=ProposedBy(actor="cortex"),
        created_at=datetime.now(tz=UTC),
    )

    new_policy = apply_action(policy, action)
    assert new_policy.version == 2
    c_a = next(c for c in new_policy.candidates if c.target == "vendorA:large")
    c_b = next(c for c in new_policy.candidates if c.target == "vendorB:fallback")
    assert c_a.weight == 0.0
    assert c_b.weight == 1.0
    assert new_policy.updated_by is not None
    assert new_policy.updated_by.actor == "cortex"


@pytest.mark.asyncio
async def test_actuator_apply_in_memory() -> None:
    actuator = Actuator(db=None)
    action = Action(
        type=ActionType.SHIFT_WEIGHT,
        params={
            "route": "order.extract",
            "from": "mock:primary",
            "to": "mock:secondary",
            "pct": 0.5,
        },
        proposed_by=ProposedBy(actor="cortex"),
    )
    res_policy = await actuator.apply(action)
    assert res_policy.version == 2
    assert action.state == ActionState.SUCCEEDED
    assert action.execution is not None
    assert action.execution.version_before == 1
    assert action.execution.version_after == 2


@pytest.mark.asyncio
async def test_create_action_api() -> None:
    from httpx import ASGITransport, AsyncClient
    from reflex_cp.main import create_app
    from reflex_cp.settings import Settings

    app = create_app(Settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/actions",
            json={
                "type": "shift_weight",
                "params": {
                    "route": "order.extract",
                    "from": "vendorA:large",
                    "to": "vendorB:fallback",
                    "pct": 1.0,
                },
                "proposed_by": {"actor": "cortex"},
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("_id") is not None
        assert data.get("state") in ("approved", "succeeded")
