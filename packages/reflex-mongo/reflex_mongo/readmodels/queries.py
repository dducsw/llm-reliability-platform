"""Read-model query functions cho Console BFF (DE-6.1, I3).

DE sở hữu các hàm query tổng hợp dữ liệu từ MongoDB.
SE chỉ việc gọi các hàm này từ FastAPI routers, không phải tự viết ad-hoc Mongo query.
"""

from __future__ import annotations

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from reflex_mongo.collections import (
    ACTIONS,
    HEALTH_STATE,
    INCIDENTS,
    INVESTIGATIONS,
    POLICIES,
    POLICY_HISTORY,
)
from reflex_mongo.readmodels.models import PulseReadModel, WarRoomReadModel


async def get_pulse(db: AsyncDatabase[dict[str, Any]]) -> PulseReadModel:
    """Tổng hợp dữ liệu cho Pulse screen: health states, open incidents, active policies."""
    health_states: list[dict[str, Any]] = []
    async for doc in db[HEALTH_STATE].find({}).limit(100):
        health_states.append(doc)

    open_incidents: list[dict[str, Any]] = []
    async for doc in db[INCIDENTS].find({"is_open": True}).sort("t.detected_at", -1).limit(20):
        open_incidents.append(doc)

    policies: list[dict[str, Any]] = []
    async for doc in db[POLICIES].find({}).limit(50):
        policies.append(doc)

    return PulseReadModel(
        health=health_states,
        incidents=open_incidents,
        policies=policies,
    )


async def list_incidents(
    db: AsyncDatabase[dict[str, Any]],
    is_open: bool | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lấy danh sách incidents kèm bộ lọc trạng thái."""
    query: dict[str, Any] = {}
    if is_open is not None:
        query["is_open"] = is_open

    items: list[dict[str, Any]] = []
    async for doc in db[INCIDENTS].find(query).sort("t.detected_at", -1).limit(limit):
        items.append(doc)
    return items


async def get_incident(
    db: AsyncDatabase[dict[str, Any]],
    key: str,
) -> dict[str, Any] | None:
    """Lấy chi tiết một incident theo key hoặc _id."""
    doc = await db[INCIDENTS].find_one({"key": key})
    if not doc:
        doc = await db[INCIDENTS].find_one({"_id": key})
    return doc


async def get_war_room(
    db: AsyncDatabase[dict[str, Any]],
    key: str,
) -> WarRoomReadModel | None:
    """Lấy trạng thái War Room: incident, các action liên quan, timeline và kết quả điều tra."""
    incident = await get_incident(db, key)
    if not incident:
        return None

    incident_id = incident.get("_id", key)
    actions: list[dict[str, Any]] = []
    async for doc in (
        db[ACTIONS]
        .find({"$or": [{"incident_id": key}, {"incident_id": incident_id}]})
        .sort("created_at", -1)
        .limit(50)
    ):
        actions.append(doc)

    investigation = await db[INVESTIGATIONS].find_one(
        {"$or": [{"incident_id": key}, {"incident_id": incident_id}]}
    )

    timeline = incident.get("timeline", [])

    return WarRoomReadModel(
        incident=incident,
        actions=actions,
        investigation=investigation,
        timeline=timeline,
    )


async def list_approvals(
    db: AsyncDatabase[dict[str, Any]],
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lấy các actions đang chờ duyệt (awaiting_approval hoặc proposed)."""
    items: list[dict[str, Any]] = []
    async for doc in (
        db[ACTIONS]
        .find({"state": {"$in": ["awaiting_approval", "proposed"]}})
        .sort("created_at", -1)
        .limit(limit)
    ):
        items.append(doc)
    return items


async def list_policies(
    db: AsyncDatabase[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Lấy danh sách toàn bộ active policies."""
    items: list[dict[str, Any]] = []
    async for doc in db[POLICIES].find({}):
        items.append(doc)
    return items


async def get_policy(
    db: AsyncDatabase[dict[str, Any]],
    route: str,
) -> dict[str, Any] | None:
    """Lấy policy hiện tại của route."""
    return await db[POLICIES].find_one({"_id": route})


async def get_policy_history(
    db: AsyncDatabase[dict[str, Any]],
    route: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lấy lịch sử thay đổi policy của route."""
    items: list[dict[str, Any]] = []
    async for doc in db[POLICY_HISTORY].find({"policy_id": route}).sort("version", -1).limit(limit):
        items.append(doc)
    return items
