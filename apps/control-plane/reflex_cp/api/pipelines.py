from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, HTTPException
from reflex_mongo.pipelines import registry

router = APIRouter()


def describe(pipeline_id: str) -> dict[str, Any]:
    module = registry.REGISTRY[pipeline_id]
    doc = inspect.getdoc(module) or ""
    return {
        "id": pipeline_id,
        "collection": getattr(module, "COLLECTION", None),
        "summary": doc.splitlines()[0] if doc else "",
        "doc": doc,
        "params": [name for name in inspect.signature(module.build).parameters],
        "source": inspect.getsource(module.build),
    }


@router.get("/api/pipelines")
async def list_pipelines() -> dict[str, Any]:
    return {"pipelines": [describe(pid) | {"source": ""} for pid in registry.REGISTRY]}


@router.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str) -> dict[str, Any]:
    if pipeline_id not in registry.REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown pipeline {pipeline_id}")
    return describe(pipeline_id)
