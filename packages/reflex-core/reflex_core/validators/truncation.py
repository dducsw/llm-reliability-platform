"""Phát hiện cắt cụt: finish_reason=length, câu/JSON dang dở."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class TruncationValidator:
    name = "no_truncation"

    def check(self, response: NormalizedResponse) -> CheckResult:
        if response.finish_reason == "length":
            return CheckResult(
                name=self.name,
                passed=False,
                reason="Response was truncated by provider (finish_reason=length)",
            )
        return CheckResult(name=self.name, passed=True)
