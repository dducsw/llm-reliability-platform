"""POST /hooks/datadog — kiểm tra X-Reflex-Webhook-Token, map monitor → signal → incident."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/hooks/datadog")
async def datadog_webhook(request: Request) -> dict:
    raise NotImplementedError
