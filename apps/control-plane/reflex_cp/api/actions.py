from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from reflex_core.actions import Action, ActionState, ActionType, ProposedBy
from reflex_mongo.collections import ACTIONS

from reflex_cp.actuator.apply import Actuator
from reflex_cp.policy_engine.decision import decide

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/actions")
async def list_actions(request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        return {"actions": []}
    cursor = db[ACTIONS].find({}).sort("created_at", -1).limit(50)
    items = []
    async for doc in cursor:
        items.append(doc)
    return {"actions": items}


@router.post("/api/actions")
async def create_action(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    actuator: Actuator = getattr(request.app.state, "actuator", Actuator(db))

    action_type = ActionType(payload.get("type", "shift_weight"))
    params = payload.get("params", {})
    incident_id = payload.get("incident_id")
    proposed_by_raw = payload.get("proposed_by", {"actor": "human"})

    now = datetime.now(tz=UTC)
    action_id = payload.get("_id") or f"act-{now.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"

    action = Action(
        _id=action_id,
        incident_id=incident_id,
        type=action_type,
        params=params,
        state=ActionState.PROPOSED,
        proposed_by=ProposedBy.model_validate(proposed_by_raw),
        created_at=now,
        updated_at=now,
    )

    # 1. Chạy policy engine guardrails & decision
    await decide(action, db)

    # 2. Nếu được auto duyệt -> thực thi qua actuator
    if action.state == ActionState.APPROVED:
        try:
            await actuator.apply(action)
        except Exception as e:
            logger.error("Error applying action %s: %s", action_id, e)
            action.state = ActionState.FAILED

    doc = action.model_dump(by_alias=True, mode="json")
    if db is not None:
        await db[ACTIONS].update_one({"_id": action_id}, {"$set": doc}, upsert=True)

    return doc


@router.post("/api/actions/{action_id}/approve")
async def approve(action_id: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    actuator: Actuator = getattr(request.app.state, "actuator", Actuator(db))

    if db is None:
        raise HTTPException(status_code=404, detail="Database not configured")

    doc = await db[ACTIONS].find_one({"_id": action_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Action not found")

    action = Action.model_validate(doc)
    action.state = ActionState.APPROVED
    action.updated_at = datetime.now(tz=UTC)

    await actuator.apply(action)
    updated_doc = action.model_dump(by_alias=True, mode="json")
    await db[ACTIONS].update_one({"_id": action_id}, {"$set": updated_doc})
    return {"ok": True, "action": updated_doc}


@router.post("/api/actions/{action_id}/reject")
async def reject(action_id: str, request: Request) -> dict[str, Any]:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=404, detail="Database not configured")

    doc = await db[ACTIONS].find_one({"_id": action_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Action not found")

    action = Action.model_validate(doc)
    action.state = ActionState.REJECTED
    action.updated_at = datetime.now(tz=UTC)

    updated_doc = action.model_dump(by_alias=True, mode="json")
    await db[ACTIONS].update_one({"_id": action_id}, {"$set": updated_doc})
    return {"ok": True, "action": updated_doc}
