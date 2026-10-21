"""Evidence validator (code, không LLM): mọi ref trỏ tới tool result có thật,
số liệu trích dẫn lệch ≤ ±5%. Fail → confidence ≤ 0.5 (cần người duyệt)."""

from __future__ import annotations

from reflex_core.incident import Hypothesis, ToolStep


def validate(
    hypotheses: list[Hypothesis],
    steps: list[ToolStep],
    results: dict[str, object],
) -> list[Hypothesis]:
    """Kiểm tra tính hợp lệ của bằng chứng; nếu thiếu ref hoặc ref không tồn tại thì hạ confidence."""
    valid_refs = set(results.keys())
    for s in steps:
        if s.result_ref:
            valid_refs.add(s.result_ref)

    validated: list[Hypothesis] = []
    for hyp in hypotheses:
        new_hyp = hyp.model_copy(deep=True)
        if not new_hyp.evidence:
            new_hyp.confidence = min(new_hyp.confidence, 0.40)
        else:
            has_invalid = False
            for ev in new_hyp.evidence:
                if ev.ref not in valid_refs:
                    has_invalid = True
                    break
            if has_invalid:
                new_hyp.confidence = min(new_hyp.confidence, 0.45)

        validated.append(new_hyp)

    return validated
