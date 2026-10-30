from typing import Any

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


@pytest.mark.asyncio
async def test_failback_step_carries_baseline_from_policy_history(fake_db: Any) -> None:
    from datetime import UTC, datetime

    from reflex_core.actions import Execution
    from reflex_mongo.collections import POLICY_HISTORY

    await fake_db[POLICY_HISTORY].insert_one(
        {
            "policy_id": "order.extract",
            "version": 7,
            "at": datetime(2026, 10, 30, tzinfo=UTC),
            "doc": {
                "candidates": [
                    {"target": "vendorA:large", "weight": 0.9},
                    {"target": "vendorB:large", "weight": 0.1},
                ]
            },
        }
    )
    parent = Action(
        type=ActionType.SHIFT_WEIGHT,
        params={
            "route": "order.extract",
            "from": "vendorA:large",
            "to": "vendorB:large",
            "pct": 1.0,
        },
        proposed_by=ProposedBy(actor="cortex"),
        execution=Execution(
            policy_id="order.extract",
            version_before=7,
            version_after=8,
            applied_at=datetime.now(tz=UTC),
        ),
    )
    step = await FailbackOrchestrator(db=fake_db).advance(parent, current_pct=50)
    assert step is not None and step.params["pct"] == 100 and step.params["baseline"] == 0.9


@pytest.mark.asyncio
async def test_baseline_uses_latest_snapshot_when_versions_repeat(fake_db: Any) -> None:
    """Sau `reflex-mongo seed` version về 1 → nhiều snapshot cùng version; phải lấy bản ngay trước khi áp dụng."""
    from datetime import UTC, datetime, timedelta

    from reflex_core.actions import Execution
    from reflex_mongo.collections import POLICY_HISTORY

    applied = datetime(2026, 10, 30, 5, 35, tzinfo=UTC)
    for at, w in [
        (applied - timedelta(days=2), 1.0),
        (applied, 0.9),
        (applied + timedelta(hours=1), 0.5),
    ]:
        await fake_db[POLICY_HISTORY].insert_one(
            {
                "policy_id": "order.extract",
                "version": 1,
                "at": at,
                "doc": {"candidates": [{"target": "vendorA:large", "weight": w}]},
            }
        )
    parent = Action(
        type=ActionType.SHIFT_WEIGHT,
        params={
            "route": "order.extract",
            "from": "vendorA:large",
            "to": "vendorB:large",
            "pct": 1.0,
        },
        proposed_by=ProposedBy(actor="rules"),
        execution=Execution(
            policy_id="order.extract", version_before=1, version_after=2, applied_at=applied
        ),
    )
    assert await FailbackOrchestrator(db=fake_db).baseline_weight(parent, "vendorA:large") == 0.9
