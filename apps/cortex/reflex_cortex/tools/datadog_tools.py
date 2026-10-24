"""dd.logs.search, dd.spans.search, dd.metrics.query — strip chaos.* (anti-cheat)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from reflex_telemetry.datadog_api import DatadogApi

from reflex_cortex.tools.base import ToolResult

_MAX_ITEMS = 20


def _window(minutes: int) -> tuple[datetime, datetime]:
    now = datetime.now(tz=UTC)
    return now - timedelta(minutes=minutes), now


def _unavailable(ref: str) -> ToolResult:
    return ToolResult(ref=ref, data=[], digest="Datadog API not configured; no data available")


def _attr(item: dict[str, Any], key: str) -> str:
    return str(item.get("attributes", {}).get(key, ""))[:160]


async def logs_search(query: str, minutes: int = 15, api: DatadogApi | None = None) -> ToolResult:
    if api is None:
        return _unavailable("dd_logs")
    frm, to = _window(minutes)
    logs = (await api.search_logs(query, frm, to, limit=_MAX_ITEMS))[:_MAX_ITEMS]
    sample = "; ".join(_attr(log, "message") for log in logs[:3])
    return ToolResult(
        ref="dd_logs",
        data=logs,
        digest=f"{len(logs)} logs for `{query}` (last {minutes}m): {sample}",
    )


async def spans_search(query: str, minutes: int = 15, api: DatadogApi | None = None) -> ToolResult:
    if api is None:
        return _unavailable("dd_spans")
    frm, to = _window(minutes)
    spans = (await api.search_spans(query, frm, to, limit=_MAX_ITEMS))[:_MAX_ITEMS]
    return ToolResult(
        ref="dd_spans", data=spans, digest=f"{len(spans)} spans for `{query}` (last {minutes}m)"
    )


async def metrics_query(query: str, minutes: int = 30, api: DatadogApi | None = None) -> ToolResult:
    if api is None:
        return _unavailable("dd_metrics")
    frm, to = _window(minutes)
    result = await api.query_metrics(query, frm, to)
    series = result.get("series", [])
    points = sum(len(s.get("pointlist", [])) for s in series)
    return ToolResult(
        ref="dd_metrics",
        data=series,
        digest=f"{len(series)} series / {points} points for `{query}` (last {minutes}m)",
    )
