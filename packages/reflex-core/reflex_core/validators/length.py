"""Kiểm tra độ dài tối thiểu/tối đa theo route."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class LengthValidator:
    name = "length"

    def check(self, response: NormalizedResponse) -> CheckResult:
        raise NotImplementedError
