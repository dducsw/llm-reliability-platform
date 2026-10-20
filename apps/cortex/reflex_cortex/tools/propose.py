"""propose_action — tool duy nhất có ghi: insert Action(state=proposed) vào `actions`.
Action phải thuộc catalog; policy engine ở control-plane quyết định."""

from __future__ import annotations

from typing import Any


async def propose_action(incident_key: str, action_type: str, params: dict[str, Any], confidence: float) -> str:
    raise NotImplementedError
