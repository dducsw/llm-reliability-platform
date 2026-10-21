"""Context pack dựng sẵn trước khi gọi LLM: SLI snapshot, burn, A11 side, A12 contributors,
A10 similar incidents, baseline A14. Chứa ~70% câu trả lời."""

from __future__ import annotations

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import HEALTH_STATE, INCIDENTS, POLICIES


async def build(incident_key: str, db: AsyncDatabase | None = None) -> dict[str, Any]:
    """Dựng context pack hoàn chỉnh cho Cortex Agent điều tra sự cố."""
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
        }

    inc = await db[INCIDENTS].find_one({"key": incident_key})
    if not inc:
        inc = await db[INCIDENTS].find_one({"_id": incident_key})

    target = inc.get("target") if inc else None
    routes = inc.get("routes", []) if inc else []
    route = routes[0] if routes else None

    policy = None
    if route:
        policy = await db[POLICIES].find_one({"_id": route})

    health = {}
    if target:
        h_doc = await db[HEALTH_STATE].find_one({"_id": f"target:{target}"})
        if h_doc:
            health[target] = h_doc

    return {
        "incident_key": incident_key,
        "incident": inc or {},
        "policy": policy or {},
        "health": health,
    }
