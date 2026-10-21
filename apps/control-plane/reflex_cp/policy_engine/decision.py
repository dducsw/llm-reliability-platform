from __future__ import annotations

from datetime import UTC, datetime

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import Action, ActionState, Decision

from reflex_cp.policy_engine.guardrails import evaluate_all


async def decide(action: Action, db: AsyncDatabase | None = None) -> Decision:
    """Đánh giá guardrails và quyết định tự động duyệt (auto) hay chờ người duyệt (human)."""
    now = datetime.now(tz=UTC)
    guardrails = await evaluate_all(action, db)

    all_pass = all(g.pass_ for g in guardrails)

    if all_pass:
        mode = "auto"
        by = "policy_engine"
        action.state = ActionState.APPROVED
    else:
        mode = "human"
        by = "policy_engine_guardrails"
        action.state = ActionState.AWAITING_APPROVAL

    decision = Decision(
        mode=mode,
        by=by,
        at=now,
        guardrails=guardrails,
    )
    action.decision = decision
    return decision
