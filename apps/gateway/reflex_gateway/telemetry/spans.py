"""APM span tags + LLMObs llm span cho từng attempt. Ghi `chaos.fault` từ header x-chaos-fault
(chỉ để kiểm chứng sau sự kiện — logic gateway KHÔNG đọc header này)."""

from __future__ import annotations


def tag_attempt_span(span: object, attrs: dict) -> None:
    raise NotImplementedError
