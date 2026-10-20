"""Pull health_state định kỳ → input global cho router (score, budget_remaining, open incident)."""

from __future__ import annotations


class HealthSync:
    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    def snapshot(self) -> dict[str, dict]:
        raise NotImplementedError
