from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NormalizedResponse:
    content: str
    finish_reason: str | None
    route: str
    tokens_out: int = 0
    streamed: bool = False


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    reason: str | None = None
    detail: dict[str, object] = field(default_factory=dict)


class Validator(Protocol):
    name: str

    def check(self, response: NormalizedResponse) -> CheckResult: ...
