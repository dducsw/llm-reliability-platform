from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

import httpx


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


class SharedClient:
    """`httpx.AsyncClient` dùng chung cho mọi request của một adapter (SE-9.2).

    Tạo client mới mỗi request = dựng SSLContext + bắt tay TCP mỗi lần → ~30ms CPU,
    gateway bão hòa ở ~25 rps. Client gắn với event loop nên tạo lại khi loop đổi (test).
    Timeout truyền theo từng request.
    """

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def get(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._client is None or self._client.is_closed or self._loop is not loop:
            self._client = httpx.AsyncClient(
                transport=self._transport,
                limits=httpx.Limits(max_connections=500, max_keepalive_connections=100),
            )
            self._loop = loop
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._loop is asyncio.get_running_loop():
            await self._client.aclose()
        self._client = None
