"""Read-only tools cho agent. Mỗi tool có JSON schema (contract test) và trả result_ref."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_telemetry.datadog_api import DatadogApi

from reflex_cortex.tools import datadog_tools, memory_tools, mongo_tools, timemachine_tools
from reflex_cortex.tools.base import ToolResult

TOOLS: dict[str, Any] = {}

ToolFn = Callable[..., Awaitable[ToolResult]]


def build_toolbox(
    db: AsyncDatabase | None, dd: DatadogApi | None, incident_key: str
) -> dict[str, ToolFn]:
    """Tool agent được phép gọi. Tool cần DB chỉ có mặt khi có DB (không trả số liệu giả)."""
    box: dict[str, ToolFn] = {
        "dd.logs_search": partial(datadog_tools.logs_search, api=dd),
        "dd.spans_search": partial(datadog_tools.spans_search, api=dd),
        "dd.metrics_query": partial(datadog_tools.metrics_query, api=dd),
        "timemachine.quick": partial(timemachine_tools.quick, incident_key),
    }
    if db is not None:
        box.update(
            {
                "mongo.sli_window": partial(mongo_tools.sli_window, db=db),
                "mongo.top_contributors": partial(mongo_tools.top_contributors, db=db),
                "mongo.blast_radius": partial(mongo_tools.blast_radius, incident_key, db=db),
                "mongo.policy_timeline": partial(mongo_tools.policy_timeline, db=db),
                "mongo.probes_compare": partial(mongo_tools.probes_compare, db=db),
                "memory.similar": partial(memory_tools.similar, incident_key, db=db),
                "memory.postmortem_search": partial(memory_tools.postmortem_search, db=db),
            }
        )
    return box
