"""Rule-based fallback classifier khi LLM lỗi/timeout — vẫn propose được action an toàn."""

from __future__ import annotations

from typing import Any

from reflex_core.incident import Recommendation


def classify(context_pack: dict[str, Any]) -> Recommendation | None:
    raise NotImplementedError
