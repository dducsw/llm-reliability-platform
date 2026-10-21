from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ToolResult:
    ref: str
    data: Any
    digest: str


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict[str, Any]

    async def __call__(self, **kwargs: Any) -> ToolResult: ...
