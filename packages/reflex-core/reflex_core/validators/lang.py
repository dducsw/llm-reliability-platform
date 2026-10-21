"""Kiểm tra ngôn ngữ trả lời (vd chat.reply phải là tiếng Việt)."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class LangValidator:
    name = "lang"

    def check(self, response: NormalizedResponse) -> CheckResult:
        raise NotImplementedError
