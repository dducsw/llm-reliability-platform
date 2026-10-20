"""Watch actions (approved) → transaction: update policy CAS + policy_history + outbox event."""

from __future__ import annotations

from reflex_core.actions import Action


class Actuator:
    async def run(self) -> None:
        raise NotImplementedError

    async def apply(self, action: Action) -> None:
        raise NotImplementedError

    async def rollback(self, action: Action) -> None:
        raise NotImplementedError
