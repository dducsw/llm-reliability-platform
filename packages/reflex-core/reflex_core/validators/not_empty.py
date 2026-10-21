"""content không rỗng / không chỉ whitespace."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class NotEmptyValidator:
    name = "not_empty"

    def check(self, response: NormalizedResponse) -> CheckResult:
        raise NotImplementedError
