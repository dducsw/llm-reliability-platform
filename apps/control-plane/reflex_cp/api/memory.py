from __future__ import annotations

import math
import random
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from reflex_mongo.collections import ACTIONS, INCIDENTS
from reflex_mongo.pipelines import a10_similar_incidents

router = APIRouter()

MAP_LIMIT = 500


def _incident_filter(incident_id: str) -> dict[str, Any]:
    return {"$or": [{"key": incident_id}, {"_id": incident_id}]}


def project_2d(vecs: list[list[float]], iters: int = 50) -> list[tuple[float, float]]:
    """PCA 2 thành phần bằng power iteration (không cần numpy; n ≤ vài trăm × 64 chiều).

    Console mô tả "UMAP 2D"; PCA giữ khoảng cách toàn cục đủ cho bản đồ ≤ 500 điểm và
    deterministic (seed cố định) nên vị trí không nhảy giữa các lần tải.
    """
    if not vecs:
        return []
    dim = len(vecs[0])
    mean = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    centered = [[v[i] - mean[i] for i in range(dim)] for v in vecs]
    rng = random.Random(7)
    comps: list[list[float]] = []
    for _ in range(2):
        w = [rng.uniform(-1, 1) for _ in range(dim)]
        for _ in range(iters):
            # w ← Xᵀ X w, trực giao hoá với thành phần trước
            scores = [sum(r[i] * w[i] for i in range(dim)) for r in centered]
            w = [sum(s * r[i] for s, r in zip(scores, centered, strict=True)) for i in range(dim)]
            for c in comps:
                dot = sum(a * b for a, b in zip(w, c, strict=True))
                w = [a - dot * b for a, b in zip(w, c, strict=True)]
            norm = math.sqrt(sum(a * a for a in w)) or 1.0
            w = [a / norm for a in w]
        comps.append(w)
    return [
        (
            round(sum(r[i] * comps[0][i] for i in range(dim)), 4),
            round(sum(r[i] * comps[1][i] for i in range(dim)), 4),
        )
        for r in centered
    ]


@router.get("/api/memory/map")
async def memory_map(request: Request, sli: str | None = None) -> dict[str, Any]:
    """Bản đồ tương đồng: mọi incident có signature, chiếu 2D + action đã giải quyết."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    flt: dict[str, Any] = {"signature.vec": {"$exists": True}}
    if sli:
        flt["sli"] = sli
    proj = {"key": 1, "sli": 1, "scope": 1, "target": 1, "status": 1, "signature.vec": 1}
    docs = [d async for d in db[INCIDENTS].find(flt, proj).limit(MAP_LIMIT)]
    docs = [d for d in docs if len((d.get("signature") or {}).get("vec") or []) > 0]
    if not docs:
        return {"points": [], "method": "pca"}
    dim = len(docs[0]["signature"]["vec"])
    docs = [d for d in docs if len(d["signature"]["vec"]) == dim]

    keys = [d.get("key") or str(d["_id"]) for d in docs]
    ids = [d["_id"] for d in docs]
    resolved_by: dict[str, dict[str, Any]] = {}
    async for a in db[ACTIONS].find(
        {"incident_id": {"$in": keys + ids}, "parent_action_id": None},
        {"incident_id": 1, "type": 1, "verification.verdict": 1},
    ):
        resolved_by.setdefault(
            str(a.get("incident_id")),
            {"type": a.get("type"), "verdict": (a.get("verification") or {}).get("verdict")},
        )

    xy = project_2d([[float(x) for x in d["signature"]["vec"]] for d in docs])
    return {
        "method": "pca",
        "points": [
            {
                "key": key,
                "sli": d.get("sli"),
                "scope": d.get("scope"),
                "target": d.get("target"),
                "status": d.get("status"),
                "action": resolved_by.get(key) or resolved_by.get(str(d["_id"])),
                "x": x,
                "y": y,
            }
            for key, d, (x, y) in zip(keys, docs, xy, strict=True)
        ],
    }


@router.get("/api/memory/similar")
async def similar(incident_id: str, request: Request, k: int = 5) -> dict[str, Any]:
    """Sự cố tương tự (A10) cho một incident: vector signature + thống kê hiệu quả action."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB not connected")
    incident = await db[INCIDENTS].find_one(_incident_filter(incident_id))
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    vec = (incident.get("signature") or {}).get("vec")
    if not vec:
        return {"incident_id": incident_id, "similar": [], "reason": "no_signature"}
    pipeline = a10_similar_incidents.build(
        vec=vec, sli=incident["sli"], scope=incident.get("scope"), k=k, current_id=incident["_id"]
    )
    return {
        "incident_id": incident_id,
        "similar": [doc async for doc in await db[INCIDENTS].aggregate(pipeline)],
    }
