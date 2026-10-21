"""Failback từng nấc 10% → 50% → 100% khi target gốc ổn định ≥ N phút."""

from __future__ import annotations


class FailbackOrchestrator:
    async def run(self) -> None:
        raise NotImplementedError
