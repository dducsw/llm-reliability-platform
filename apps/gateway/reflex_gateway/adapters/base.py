from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class UpstreamResult:
    status: int
    content: str
    finish_reason: str | None
    tokens_in: int
    tokens_out: int
    latency_ms: float
    ttft_ms: float | None
    raw: dict
    error_class: str | None = None


class Adapter(Protocol):
    name: str

    async def complete(self, target: dict, payload: dict, timeout_s: float) -> UpstreamResult: ...

    def stream(self, target: dict, payload: dict, timeout_s: float) -> AsyncIterator[dict]: ...
