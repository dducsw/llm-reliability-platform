"""APM span tags + LLMObs llm span cho từng attempt. Ghi `chaos.fault` từ header x-chaos-fault
(chỉ để kiểm chứng sau sự kiện — logic gateway KHÔNG đọc header này)."""

from __future__ import annotations

from reflex_telemetry import tags as t

_ATTR_TAGS = {
    "route": t.ROUTE,
    "target": t.TARGET,
    "attempt_kind": t.ATTEMPT_KIND,
    "outcome": t.OUTCOME,
    "policy_version": t.POLICY_VERSION,
    "gateway_id": t.GATEWAY_ID,
    "chaos_fault": t.CHAOS_FAULT,
}


def tag_attempt_span(span: object, attrs: dict) -> None:
    """Gắn tag lên span hiện tại; `span=None` (tracing tắt) thì bỏ qua."""
    set_tag = getattr(span, "set_tag", None)
    if set_tag is None:
        return
    for key, tag in _ATTR_TAGS.items():
        value = attrs.get(key)
        if value is not None:
            set_tag(tag, value)


def current_span() -> object | None:
    try:
        from ddtrace import tracer

        return tracer.current_span()
    except Exception:
        return None
