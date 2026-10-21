"""mongo.sli_window, mongo.top_contributors (A12), mongo.blast_radius (A13), mongo.policy_timeline."""

from __future__ import annotations

from typing import Any

from reflex_cortex.tools.base import ToolResult


async def sli_window(scope: str, key: str, minutes: int = 30) -> ToolResult:
    raise NotImplementedError


async def top_contributors(target: str, minutes: int = 15) -> ToolResult:
    raise NotImplementedError


async def blast_radius(incident_key: str) -> ToolResult:
    raise NotImplementedError


async def policy_timeline(route: str, minutes: int = 60) -> ToolResult:
    raise NotImplementedError


async def probes_compare(target: str, minutes: int = 15) -> ToolResult:
    """A11 — direct vs via_gateway."""
    raise NotImplementedError


_ = Any
