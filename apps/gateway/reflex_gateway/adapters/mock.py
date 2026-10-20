"""Adapter `mock` — chuẩn hóa usage, finish_reason, lỗi."""

from __future__ import annotations

from collections.abc import AsyncIterator

from reflex_gateway.adapters.base import UpstreamResult


class MockAdapter:
    name = "mock"

    async def complete(self, target: dict, payload: dict, timeout_s: float) -> UpstreamResult:
        raise NotImplementedError

    def stream(self, target: dict, payload: dict, timeout_s: float) -> AsyncIterator[dict]:
        raise NotImplementedError
