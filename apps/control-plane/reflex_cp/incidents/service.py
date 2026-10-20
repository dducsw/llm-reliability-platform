from __future__ import annotations


class IncidentService:
    async def open_or_merge(self, signal: dict, slo_id: str, target: str | None, route: str | None) -> dict:
        raise NotImplementedError

    async def transition(self, key: str, status: str, actor: str, ref: str | None = None) -> None:
        raise NotImplementedError

    async def compute_signature(self, key: str) -> None:
        """A8 first-bad-at + A9 signature vector."""
        raise NotImplementedError

    async def compute_impact(self, key: str) -> None:
        """A13 blast radius."""
        raise NotImplementedError
