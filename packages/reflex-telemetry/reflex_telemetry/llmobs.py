"""LLMObs span helpers: agent / workflow / tool / llm. No-op khi LLMObs chưa bật
(test, local không có DD_API_KEY) nên code gọi không cần kiểm tra."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

logger = logging.getLogger(__name__)

Kind = Literal["agent", "workflow", "tool", "llm", "task"]


def enabled() -> bool:
    try:
        from ddtrace.llmobs import LLMObs

        return bool(LLMObs.enabled)
    except Exception:
        return False


@contextmanager
def span(kind: Kind, name: str, **kwargs: Any) -> Iterator[Any | None]:
    """`with span("tool", "dd.logs_search") as s:` — `s` là None khi LLMObs tắt."""
    if not enabled():
        yield None
        return
    from ddtrace.llmobs import LLMObs

    with getattr(LLMObs, kind)(name=name, **kwargs) as s:
        yield s


def annotate(s: Any | None, **kwargs: Any) -> None:
    """LLMObs.annotate an toàn: span None → bỏ qua; lỗi annotate không được làm hỏng request."""
    if s is None:
        return
    try:
        from ddtrace.llmobs import LLMObs

        LLMObs.annotate(span=s, **kwargs)
    except Exception as e:
        logger.debug("LLMObs.annotate failed: %s", e)
