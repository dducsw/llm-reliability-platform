"""dd.logs.search, dd.spans.search, dd.metrics.query — strip chaos.* (anti-cheat)."""

from __future__ import annotations

from reflex_cortex.tools.base import ToolResult


async def logs_search(query: str, minutes: int = 15) -> ToolResult:
    raise NotImplementedError


async def spans_search(query: str, minutes: int = 15) -> ToolResult:
    raise NotImplementedError


async def metrics_query(query: str, minutes: int = 30) -> ToolResult:
    raise NotImplementedError
