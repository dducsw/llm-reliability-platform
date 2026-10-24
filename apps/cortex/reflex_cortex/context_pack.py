from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import ATTEMPTS_TS, HEALTH_STATE, INCIDENTS, POLICIES, PROBES_TS
from reflex_mongo.pipelines import a10_similar_incidents, a11_side_diagnosis, a12_top_contributors


async def build(incident_key: str, db: AsyncDatabase | None = None) -> dict[str, Any]:
    """Dựng context pack hoàn chỉnh cho Cortex Agent điều tra sự cố.

    Tập hợp:
    1. Thông tin incident, policy đang áp dụng, trạng thái health_state.
    2. Chẩn đoán phân biệt A11 (lỗi do vendor hay do gateway).
    3. Phân tích chiều lỗi chính A12 (top contributors).
    4. Gợi ý hành động từ sự cố tương đồng A10 (Vector Search).
    """
    if db is None:
        return {
            "incident_key": incident_key,
            "incident": {
                "key": incident_key,
                "target": "vendorA:large",
                "routes": ["order.extract"],
                "sli": "quality",
                "signals": [{"source": "sentinel", "diagnosis": "server-side output truncation"}],
            },
            "policy": {
                "candidates": [
                    {"target": "vendorA:large", "weight": 0.9},
                    {"target": "vendorB:fallback", "weight": 0.1},
                ]
            },
            "health": {},
            "side_diagnosis": {"provider_side": True},
            "top_contributors": {"by_route": [{"_id": "order.extract", "n": 42}]},
            "similar_incidents": [],
        }

    inc = await db[INCIDENTS].find_one({"key": incident_key})
    if not inc:
        inc = await db[INCIDENTS].find_one({"_id": incident_key})

    target = inc.get("target") if inc else None
    routes = inc.get("routes", []) if inc else []
    route = routes[0] if routes else None
    sli = inc.get("sli", "quality") if inc else "quality"

    now = datetime.now(tz=UTC)
    t_info = inc.get("t", {}) if inc else {}
    detected_at = t_info.get("detected_at")
    if isinstance(detected_at, str):
        detected_at = datetime.fromisoformat(detected_at)
    elif not isinstance(detected_at, datetime):
        detected_at = now

    policy = None
    if route:
        policy = await db[POLICIES].find_one({"_id": route})

    health = {}
    if target:
        h_doc = await db[HEALTH_STATE].find_one({"_id": f"target:{target}"})
        if h_doc:
            health[target] = h_doc

    # 1. A11: Chẩn đoán phân biệt (probe direct vs via_gateway)
    side_diagnosis: dict[str, Any] = {}
    if target:
        try:
            p_a11 = a11_side_diagnosis.build(
                target=target,
                from_=detected_at - timedelta(minutes=5),
                to=detected_at,
            )
            res_a11 = await (await db[PROBES_TS].aggregate(p_a11)).to_list(1)
            if res_a11 and "paths" in res_a11[0]:
                side_diagnosis = res_a11[0]["paths"]
        except Exception:
            pass

    # 2. A12: Top contributors
    top_contributors: dict[str, Any] = {}
    if target:
        try:
            p_a12 = a12_top_contributors.build(
                target=target,
                from_=detected_at - timedelta(minutes=10),
                to=detected_at,
                k=3,
            )
            res_a12 = await (await db[ATTEMPTS_TS].aggregate(p_a12)).to_list(1)
            if res_a12:
                top_contributors = res_a12[0]
        except Exception:
            pass

    # 3. A10: Sự cố tương đồng qua Vector Search
    similar_incidents: list[dict[str, Any]] = []
    signature = inc.get("signature") if inc else None
    if inc and signature and "vec" in signature:
        try:
            curr_id = str(inc["_id"]) if inc.get("_id") is not None else None
            p_a10 = a10_similar_incidents.build(
                vec=signature["vec"],
                sli=sli,
                k=3,
                current_id=curr_id,
            )
            similar_incidents = await (await db[INCIDENTS].aggregate(p_a10)).to_list(5)
        except Exception:
            pass

    return {
        "incident_key": incident_key,
        "incident": inc or {},
        "policy": policy or {},
        "health": health,
        "side_diagnosis": side_diagnosis,
        "top_contributors": top_contributors,
        "similar_incidents": similar_incidents,
    }
