"""propose_action — tool duy nhất có ghi: insert Action(state=proposed) vào `actions`.
Action phải thuộc catalog; policy engine ở control-plane quyết định.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import (
    Action,
    ActionState,
    ActionType,
    ProposedBy,
    validate_params,
)
from reflex_mongo.collections import ACTIONS


async def propose_action(
    incident_key: str,
    action_type: str,
    params: dict[str, Any],
    confidence: float,
    db: AsyncDatabase | None = None,
) -> str:
    """Ghi nhận hành động do Cortex đề xuất vào collection actions."""
    act_type = ActionType(action_type)
    # Validate tham số hành động theo JSON Schema của catalog
    validate_params(act_type, params)

    now = datetime.now(tz=UTC)
    action_id = f"act-{now.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"

    action = Action(
        _id=action_id,
        incident_id=incident_key,
        type=act_type,
        params=params,
        state=ActionState.PROPOSED,
        proposed_by=ProposedBy(actor="cortex"),
        created_at=now,
        updated_at=now,
    )

    if db is not None:
        doc = action.model_dump(by_alias=True, mode="json")
        await db[ACTIONS].insert_one(doc)

    return action_id
