from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/incidents")
async def list_incidents() -> dict:
    raise NotImplementedError


@router.get("/api/incidents/{key}")
async def get_incident(key: str) -> dict:
    raise NotImplementedError


@router.post("/api/incidents/{key}/ack")
async def ack(key: str) -> dict:
    raise NotImplementedError


@router.post("/api/incidents/{key}/false-positive")
async def false_positive(key: str) -> dict:
    raise NotImplementedError
