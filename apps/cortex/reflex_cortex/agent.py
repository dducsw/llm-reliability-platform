"""Reasoning loop: LLM (qua gateway) + read-only tools, ≤ 12 tool calls, ≤ 90s, structured output.
LLMObs: agent → workflow → tool → llm span, tag incident_id."""

from __future__ import annotations

from reflex_core.incident import Investigation


class CortexAgent:
    async def investigate(self, incident_key: str) -> Investigation:
        raise NotImplementedError
