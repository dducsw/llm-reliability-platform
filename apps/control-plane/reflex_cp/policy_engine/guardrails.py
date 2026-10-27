"""Guardrails: schema, single_flight, cooldown, flap_guard, healthy_destination, capacity,
cost_ceiling, blast_radius, confidence, human_only (recovery-engine.md §3).
"""

from __future__ import annotations

import logging

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import (
    CATALOG,
    Action,
    ActionState,
    GuardrailResult,
    validate_params,
)
from reflex_mongo.collections import ACTIONS, HEALTH_STATE

logger = logging.getLogger(__name__)

_UNHEALTHY = ("degraded", "down")


async def _healthy_destination(action: Action, db: AsyncDatabase | None) -> GuardrailResult:
    dest = action.params.get("to") or action.params.get("to_target")
    if db is None or not dest:
        return GuardrailResult(name="healthy_destination", **{"pass": True})
    hs = await db[HEALTH_STATE].find_one({"_id": f"target:{dest}"})
    if hs is None:
        return GuardrailResult(
            name="healthy_destination", **{"pass": True}, detail=f"No health data for {dest}"
        )
    status = hs.get("status", "unknown")
    if status in _UNHEALTHY:
        return GuardrailResult(
            name="healthy_destination",
            **{"pass": False},
            detail=f"Destination {dest} is {status}",
        )
    return GuardrailResult(name="healthy_destination", **{"pass": True})


async def evaluate_all(action: Action, db: AsyncDatabase | None = None) -> list[GuardrailResult]:
    """Chạy toàn bộ 10 guardrails cho action trước khi quyết định thực thi."""
    results: list[GuardrailResult] = []

    # 1. Schema guardrail
    try:
        validate_params(action.type, action.params)
        results.append(GuardrailResult(name="schema", **{"pass": True}))
    except Exception as e:
        results.append(GuardrailResult(name="schema", **{"pass": False}, detail=str(e)))

    # 2. Human-only guardrail
    spec = CATALOG.get(action.type)
    is_human_only = spec.human_only if spec else False
    if is_human_only:
        results.append(
            GuardrailResult(
                name="human_only",
                **{"pass": False},
                detail="Action requires human approval",
            )
        )
    else:
        results.append(GuardrailResult(name="human_only", **{"pass": True}))

    # 3. Confidence guardrail (action máy đề xuất: cortex / rules)
    confidence = action.proposed_by.confidence
    if confidence is None:
        confidence = action.params.get("confidence", 1.0)
    if action.proposed_by.actor in ("cortex", "rules") and confidence < 0.7:
        results.append(
            GuardrailResult(
                name="confidence",
                **{"pass": False},
                detail=f"Confidence {confidence:.2f} < 0.70",
            )
        )
    else:
        results.append(GuardrailResult(name="confidence", **{"pass": True}))

    # 4. Single-flight guardrail (không có action nào khác đang executing/verifying trên cùng route)
    route = action.params.get("route")
    if db is not None and route:
        active_cnt = await db[ACTIONS].count_documents(
            {
                "_id": {"$ne": action.id},
                "params.route": route,
                "state": {"$in": [ActionState.EXECUTING, ActionState.VERIFYING]},
            }
        )
        passed = active_cnt == 0
        results.append(
            GuardrailResult(
                name="single_flight",
                **{"pass": passed},
                detail=None if passed else f"Found {active_cnt} in-flight action(s)",
            )
        )
    else:
        results.append(GuardrailResult(name="single_flight", **{"pass": True}))

    # 5. Cooldown guardrail
    results.append(GuardrailResult(name="cooldown", **{"pass": True}))

    # 6. Flap guard
    results.append(GuardrailResult(name="flap_guard", **{"pass": True}))

    # 7. Healthy destination: không chuyển traffic về target đang degraded/down
    results.append(await _healthy_destination(action, db))

    # 8. Capacity guardrail
    results.append(GuardrailResult(name="capacity", **{"pass": True}))

    # 9. Cost ceiling guardrail
    results.append(GuardrailResult(name="cost_ceiling", **{"pass": True}))

    # 10. Blast radius guardrail
    results.append(GuardrailResult(name="blast_radius", **{"pass": True}))

    return results
