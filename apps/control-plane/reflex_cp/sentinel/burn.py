"""A4 + A5: burn rate đa cửa sổ & budget còn lại cho mọi SLO (theo profile)."""

from __future__ import annotations


class BurnEvaluator:
    async def evaluate(self) -> list[dict]:
        raise NotImplementedError
