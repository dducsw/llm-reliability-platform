"""Hàm thuần: (policy, action) → policy mới cho từng ActionType."""

from __future__ import annotations

from datetime import UTC, datetime

from reflex_core.actions import (
    Action,
    ActionType,
    EnableHedgingParams,
    OpenCircuitGlobalParams,
    ShiftWeightParams,
)
from reflex_core.policy import Policy, UpdatedBy


def apply_action(policy: Policy, action: Action) -> Policy:
    """Áp dụng Action lên Policy để tạo ra Policy mới (phiên bản tăng thêm 1)."""
    new_p = policy.model_copy(deep=True)

    if action.type == ActionType.SHIFT_WEIGHT:
        params = ShiftWeightParams.model_validate(action.params)
        from_cand = next((c for c in new_p.candidates if c.target == params.from_), None)
        to_cand = next((c for c in new_p.candidates if c.target == params.to), None)

        if from_cand is not None and to_cand is not None:
            shift_amt = from_cand.weight * params.pct
            from_cand.weight = max(0.0, round(from_cand.weight - shift_amt, 4))
            to_cand.weight = round(to_cand.weight + shift_amt, 4)

            # Chuẩn hóa tổng weights = 1.0 nếu có candidates
            total = sum(c.weight for c in new_p.candidates)
            if total > 0:
                for c in new_p.candidates:
                    c.weight = round(c.weight / total, 4)

    elif action.type == ActionType.OPEN_CIRCUIT_GLOBAL:
        params = OpenCircuitGlobalParams.model_validate(action.params)
        target_cand = next((c for c in new_p.candidates if c.target == params.target), None)
        if target_cand is not None:
            target_cand.weight = 0.0
            others = [c for c in new_p.candidates if c.target != params.target]
            total_other = sum(c.weight for c in others)
            if total_other > 0:
                for c in others:
                    c.weight = round(c.weight / total_other, 4)

    elif action.type == ActionType.ENABLE_HEDGING:
        params = EnableHedgingParams.model_validate(action.params)
        new_p.hedge.enabled = True
        new_p.hedge.after = params.after
        new_p.hedge.max_extra_cost_ratio = params.max_cost

    # Cập nhật thông tin version và audit log
    new_p.version += 1
    new_p.updated_at = datetime.now(tz=UTC)
    new_p.updated_by = UpdatedBy(
        actor=action.proposed_by.actor,
        action_id=action.id,
        reason=f"applied_{action.type}",
    )

    return new_p
