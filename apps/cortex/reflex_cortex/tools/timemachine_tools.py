"""timemachine.quick — replay nhanh 1 variant để ước lượng hiệu quả action."""

from __future__ import annotations

from reflex_cortex.tools.base import ToolResult


async def quick(incident_key: str, action_type: str, params: dict) -> ToolResult:
    """Chưa có DES engine (làn DE) → báo rõ là không khả dụng thay vì bịa ước lượng."""
    return ToolResult(
        ref="tm_quick",
        data={"available": False, "incident_key": incident_key, "action_type": action_type},
        digest="Time Machine not available yet; no counterfactual estimate",
    )
