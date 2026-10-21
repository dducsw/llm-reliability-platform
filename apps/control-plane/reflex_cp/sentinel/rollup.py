"""Tick 10s: chạy A1/A2 (raw → sli_1m), A3 định kỳ (sli_1m → sli_1h)."""

from __future__ import annotations


class RollupJob:
    async def tick(self) -> None:
        raise NotImplementedError
