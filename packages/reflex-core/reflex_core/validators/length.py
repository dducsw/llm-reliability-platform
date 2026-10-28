"""Kiểm tra độ dài tối thiểu/tối đa theo route.

Khai báo trong policy: "length:20-4000" (số ký tự, sau khi strip), "length:20-" (chỉ min).
"""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class LengthValidator:
    name = "length"

    def __init__(self, min_chars: int = 1, max_chars: int | None = None) -> None:
        self.min_chars = min_chars
        self.max_chars = max_chars

    @classmethod
    def from_spec(cls, arg: str) -> LengthValidator:
        lo, _, hi = arg.partition("-")
        return cls(int(lo) if lo else 1, int(hi) if hi else None)

    def check(self, response: NormalizedResponse) -> CheckResult:
        n = len(response.content.strip())
        detail: dict[str, object] = {"chars": n}
        if n < self.min_chars:
            return CheckResult(
                name=self.name,
                passed=False,
                reason=f"Response too short ({n} < {self.min_chars} chars)",
                detail=detail,
            )
        if self.max_chars is not None and n > self.max_chars:
            return CheckResult(
                name=self.name,
                passed=False,
                reason=f"Response too long ({n} > {self.max_chars} chars)",
                detail=detail,
            )
        return CheckResult(name=self.name, passed=True, detail=detail)
