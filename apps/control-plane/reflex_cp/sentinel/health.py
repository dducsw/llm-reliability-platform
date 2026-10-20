"""Ghi health_state (watched) cho từng target/route: status, sli, burn, budget, score."""

from __future__ import annotations


class HealthWriter:
    async def write(self, evaluations: list[dict]) -> None:
        raise NotImplementedError
