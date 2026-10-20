from __future__ import annotations

from reflex_core.actions import Action, Decision


async def decide(action: Action) -> Decision:
    raise NotImplementedError
