"""memory.similar (A10 $vectorSearch), memory.postmortem_search (Atlas Search)."""

from __future__ import annotations

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import INCIDENTS, POSTMORTEMS
from reflex_mongo.pipelines import a10_similar_incidents

from reflex_cortex.tools.base import ToolResult


async def similar(incident_key: str, k: int = 5, db: AsyncDatabase | None = None) -> ToolResult:
    if db is None:
        return ToolResult(
            ref="mem_similar", data=[], digest="Incident Memory unavailable (no database)"
        )
    inc = await db[INCIDENTS].find_one({"$or": [{"key": incident_key}, {"_id": incident_key}]})
    vec = ((inc or {}).get("signature") or {}).get("vec")
    if not inc or not vec:
        return ToolResult(
            ref="mem_similar",
            data=[],
            digest="No signature for this incident yet; nothing to match",
        )
    pipeline = a10_similar_incidents.build(
        vec=vec, sli=inc["sli"], scope=inc.get("scope"), k=k, current_id=inc.get("_id")
    )
    rows: list[dict[str, Any]] = [doc async for doc in await db[INCIDENTS].aggregate(pipeline)]
    return ToolResult(
        ref="mem_similar",
        data=rows,
        digest=f"{len(rows)} similar resolved incidents with measured action outcomes",
    )


async def postmortem_search(text: str, k: int = 5, db: AsyncDatabase | None = None) -> ToolResult:
    if db is None:
        return ToolResult(
            ref="mem_postmortem", data=[], digest="Postmortem search unavailable (no database)"
        )
    pipeline = [
        {
            "$search": {
                "index": "postmortems_text",
                "text": {"query": text, "path": ["title", "summary", "body_md"]},
            }
        },
        {"$limit": k},
        {"$project": {"title": 1, "summary": 1, "tags": 1, "score": {"$meta": "searchScore"}}},
    ]
    rows = [doc async for doc in await db[POSTMORTEMS].aggregate(pipeline)]
    return ToolResult(
        ref="mem_postmortem", data=rows, digest=f"{len(rows)} postmortems matching `{text[:60]}`"
    )
