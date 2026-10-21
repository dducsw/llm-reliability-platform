"""Context pack dựng sẵn trước khi gọi LLM: SLI snapshot, burn, A11 side, A12 contributors,
A10 similar incidents, baseline A14. Chứa ~70% câu trả lời."""

from __future__ import annotations

from typing import Any


async def build(incident_key: str) -> dict[str, Any]:
    raise NotImplementedError
