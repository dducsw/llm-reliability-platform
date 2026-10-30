"""Read-model query functions cho Console BFF (DE-6.1, I3).

DE sở hữu các hàm query tổng hợp dữ liệu từ MongoDB.
SE chỉ việc gọi các hàm này từ FastAPI routers, không phải tự viết ad-hoc Mongo query.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from reflex_mongo.collections import (
    ACTIONS,
    HEALTH_STATE,
    INCIDENTS,
    INVESTIGATIONS,
    POLICIES,
    POLICY_HISTORY,
    POSTMORTEMS,
    SLI_1M,
)
from reflex_mongo.readmodels.models import PulseKpis, PulseReadModel, WarRoomReadModel


def _p50(values: list[float]) -> float | None:
    """Trung vị chuẩn Python (số liệu nhỏ, không cần $percentile approximate)."""
    if not values:
        return None
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def _json_safe(doc: dict[str, Any]) -> dict[str, Any]:
    """Pydantic/FastAPI không serialize ObjectId: đế ở biên trả về."Doc copy 1 tầng."""
    out = dict(doc)
    oid = out.get("_id")
    if oid is not None and not isinstance(oid, str):
        out["_id"] = str(oid)
    return out


async def get_pulse_kpis(db: AsyncDatabase[dict[str, Any]]) -> PulseKpis:
    """KPI strip cho Pulse.

    - quality/availability: sli_1m scope=route (Delivered ledger, A2), cửa sổ 60 phút.
    - MTTD/MTTR p50: incidents resolved/trong 7 ngày; định nghĩa thời lượng theo A17.
    - Chi phí hôm nay: sli_1m scope=route, ngày dương lịch chuẩn Asia/Ho_Chi_Minh (A18).
    """
    now = datetime.now(tz=UTC)

    # Delivered ledger 60 phút gần nhất: một group duy nhất, đủ cho cả quality lẫn availability.
    pipeline = [
        {"$match": {"scope": "route", "ts": {"$gte": now - timedelta(minutes=60)}}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": "$total"},
                "ok": {"$sum": "$ok"},
                "q_eligible": {"$sum": "$q_eligible"},
                "q_good": {"$sum": "$q_good"},
            }
        },
    ]
    cursor = await db[SLI_1M].aggregate(pipeline)
    agg = await cursor.to_list(1)
    quality = availability = None
    if agg:
        if agg[0]["q_eligible"]:
            quality = agg[0]["q_good"] / agg[0]["q_eligible"]
        if agg[0]["total"]:
            availability = agg[0]["ok"] / agg[0]["total"]

    # MTTX 7 ngày: fetch rồi tính p50 ở đây cho chính xác tuyệt đối; khối lượng demo nhỏ.
    mttds: list[float] = []
    mttrs: list[float] = []
    since = now - timedelta(days=7)
    async for doc in db[INCIDENTS].find({"t.detected_at": {"$gte": since}}):
        t = doc.get("t") or {}
        detected, first_bad, resolved = (
            t.get("detected_at"),
            t.get("first_bad_at"),
            t.get("resolved_at"),
        )
        if detected and first_bad:
            mttds.append((detected - first_bad).total_seconds())
        if resolved and first_bad:
            mttrs.append((resolved - first_bad).total_seconds())

    # Hôm nay (VN): chỉ tính delivery-side (scope=route) để không đếm kép chi phí hedge/retry.
    vn = timezone(timedelta(hours=7))  # Asia/Ho_Chi_Minh theo A18
    start_today = (
        datetime.now(tz=vn).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    )
    cost_pipeline = [
        {"$match": {"scope": "route", "ts": {"$gte": start_today}}},
        {
            "$group": {
                "_id": None,
                "cost_usd": {"$sum": "$cost_usd"},
                "tokens_in": {"$sum": "$tokens_in"},
                "tokens_out": {"$sum": "$tokens_out"},
                "requests": {"$sum": "$total"},
            }
        },
    ]
    cursor = await db[SLI_1M].aggregate(cost_pipeline)
    cost = await cursor.to_list(1)
    c = cost[0] if cost else {}

    return PulseKpis(
        quality=quality,
        availability=availability,
        mttd_p50_s=_p50(mttds),
        mttr_p50_s=_p50(mttrs),
        cost_usd_today=float(c.get("cost_usd") or 0.0),
        tokens_in_today=int(c.get("tokens_in") or 0),
        tokens_out_today=int(c.get("tokens_out") or 0),
        requests_today=int(c.get("requests") or 0),
    )


async def get_pulse(db: AsyncDatabase[dict[str, Any]]) -> PulseReadModel:
    """Tổng hợp dữ liệu cho Pulse screen: health states, open incidents, active policies."""
    health_states: list[dict[str, Any]] = []
    async for doc in db[HEALTH_STATE].find({}).limit(100):
        health_states.append(doc)

    open_incidents: list[dict[str, Any]] = []
    async for doc in db[INCIDENTS].find({"is_open": True}).sort("t.detected_at", -1).limit(20):
        open_incidents.append(_json_safe(doc))

    policies: list[dict[str, Any]] = []
    async for doc in db[POLICIES].find({}).limit(50):
        policies.append(doc)

    return PulseReadModel(
        health=health_states,
        incidents=open_incidents,
        policies=policies,
        kpis=await get_pulse_kpis(db),
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
        items.append(_json_safe(doc))
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
        actions.append(_json_safe(doc))

    investigation = await db[INVESTIGATIONS].find_one(
        {"$or": [{"incident_id": key}, {"incident_id": incident_id}]}
    )

    timeline = incident.get("timeline", [])

    # Cortex soạn postmortem lúc resolved (pm-{key}); resolved cũ vẫn có để xem lại.
    postmortem = await db[POSTMORTEMS].find_one({"incident_id": incident_id}) or await db[
        POSTMORTEMS
    ].find_one({"incident_id": key})

    return WarRoomReadModel(
        incident=incident,
        actions=actions,
        investigation=investigation,
        timeline=timeline,
        postmortem=postmortem,
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
        items.append(_json_safe(doc))
    return items
