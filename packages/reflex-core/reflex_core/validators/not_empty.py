"""content không rỗng / không chỉ whitespace."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class NotEmptyValidator:
    name = "not_empty"

    def check(self, response: NormalizedResponse) -> CheckResult:
        passed = bool(response.content and response.content.strip())
        return CheckResult(
            name=self.name, passed=passed, reason=None if passed else "Content is empty"
        )
