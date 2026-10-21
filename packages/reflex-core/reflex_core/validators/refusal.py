"""Phát hiện câu từ chối mẫu của model (vi + en)."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse

_REFUSAL_PHRASES = (
    "i cannot",
    "i can't",
    "as an ai",
    "i am an ai",
    "tôi không thể",
    "tôi là một ai",
    "xin lỗi, tôi không thể",
)


class RefusalValidator:
    name = "refusal"

    def check(self, response: NormalizedResponse) -> CheckResult:
        lower = response.content.lower()
        for phrase in _REFUSAL_PHRASES:
            if phrase in lower:
                return CheckResult(
                    name=self.name,
                    passed=False,
                    reason=f"Model refusal detected: contains '{phrase}'",
                )
        return CheckResult(name=self.name, passed=True)
