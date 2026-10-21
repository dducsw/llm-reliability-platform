"""Evidence validator (code, không LLM): mọi ref trỏ tới tool result có thật,
số liệu trích dẫn lệch ≤ ±5%. Fail → confidence ≤ 0.5 (cần người duyệt)."""

from __future__ import annotations

from reflex_core.incident import Hypothesis, ToolStep


def validate(hypotheses: list[Hypothesis], steps: list[ToolStep], results: dict[str, object]) -> list[Hypothesis]:
    raise NotImplementedError
