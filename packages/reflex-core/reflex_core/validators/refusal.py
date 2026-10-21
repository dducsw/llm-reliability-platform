"""Phát hiện câu từ chối mẫu của model (vi + en)."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class RefusalValidator:
    name = "refusal"

    def check(self, response: NormalizedResponse) -> CheckResult:
        raise NotImplementedError
