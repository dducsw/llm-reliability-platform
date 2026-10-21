"""Cache collection `targets` (giá, adapter, base_url, capacity_hint)."""

from __future__ import annotations


class TargetCatalog:
    async def load(self) -> None:
        raise NotImplementedError

    def get(self, target_id: str) -> dict:
        raise NotImplementedError
