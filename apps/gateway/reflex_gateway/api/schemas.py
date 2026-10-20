"""Request/response models theo chuẩn OpenAI Chat Completions + envelope lỗi (reflex.reason)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None


class ChatCompletionRequest(BaseModel):
    model: str = "reflex/auto"  # "target:<id>" để ép target
    messages: list[ChatMessage]
    stream: bool = False
    max_tokens: int | None = None
    temperature: float | None = None
    response_format: dict[str, Any] | None = None


class ReflexErrorReason(BaseModel):
    reason: Literal["shed", "deadline", "all_targets_unavailable", "quality_exhausted"]


class ErrorBody(BaseModel):
    message: str
    type: str
    code: str | None = None
    reflex: ReflexErrorReason | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
