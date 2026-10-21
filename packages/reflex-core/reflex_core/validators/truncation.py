"""Phát hiện cắt cụt: finish_reason=length, câu/JSON dang dở."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class TruncationValidator:
    name = "truncation"

    def check(self, response: NormalizedResponse) -> CheckResult:
        raise NotImplementedError
