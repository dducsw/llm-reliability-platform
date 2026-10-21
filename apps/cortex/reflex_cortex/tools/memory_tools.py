"""memory.similar (A10 $vectorSearch), memory.postmortem_search (Atlas Search)."""

from __future__ import annotations

from reflex_cortex.tools.base import ToolResult


async def similar(incident_key: str, k: int = 5) -> ToolResult:
    raise NotImplementedError


async def postmortem_search(text: str, k: int = 5) -> ToolResult:
    raise NotImplementedError
