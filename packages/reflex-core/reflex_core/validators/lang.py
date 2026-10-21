"""Kiểm tra ngôn ngữ trả lời (vd chat.reply phải là tiếng Việt)."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse

# Một số từ tiếng Việt phổ biến để nhận diện cơ bản
_VI_WORDS = ("và", "của", "là", "có", "được", "trong", "để", "cho", "với", "không", "quý khách", "bạn", "ạ", "dạ")


class LangValidator:
    name = "lang"

    def check(self, response: NormalizedResponse) -> CheckResult:
        if response.route == "chat.reply":
            lower = response.content.lower()
            found = any(w in lower for w in _VI_WORDS)
            if not found and len(response.content.split()) > 4:
                return CheckResult(name=self.name, passed=False, reason="Response does not appear to be Vietnamese")
        return CheckResult(name=self.name, passed=True)
