"""POST /v1/chat/completions — OpenAI-compatible (docs/60-interface/api-contracts.md §1).

Headers vào: x-reflex-route (bắt buộc), x-priority, x-reflex-session, x-reflex-deadline-ms.
Headers ra:  x-reflex-target, x-reflex-attempts, x-reflex-policy-version,
             x-reflex-request-id, x-reflex-quality.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    raise NotImplementedError


@router.get("/v1/models")
async def list_models() -> dict:
    raise NotImplementedError
