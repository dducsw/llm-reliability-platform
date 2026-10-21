"""Danh mục tag & metric chuẩn (docs/40-observability/datadog-architecture.md)."""

from __future__ import annotations

from typing import Final

# Tags
ENV: Final = "env"
SERVICE: Final = "service"
VERSION: Final = "version"
ROUTE: Final = "route"
TARGET: Final = "target"
ATTEMPT_KIND: Final = "attempt_kind"
OUTCOME: Final = "outcome"
INCIDENT_ID: Final = "incident_id"
POLICY_VERSION: Final = "policy_version"
PATH: Final = "path"
GATEWAY_ID: Final = "gateway_id"
CHAOS_FAULT: Final = "chaos.fault"  # chỉ span tag; lọc khỏi input của Cortex

# Service names
SVC_GATEWAY: Final = "reflex-gateway"
SVC_CONTROL_PLANE: Final = "reflex-control-plane"
SVC_CORTEX: Final = "reflex-cortex"
SVC_MOCK_LLM: Final = "reflex-mock-llm"
SVC_CHAOS_PROXY: Final = "reflex-chaos-proxy"
SVC_TRAFFIC: Final = "reflex-traffic"
SVC_PROBER: Final = "reflex-prober"

# Metrics
M_REQUEST: Final = "reflex.request"
M_REQUEST_LATENCY: Final = "reflex.request.latency"
M_ATTEMPT: Final = "reflex.attempt"
M_ATTEMPT_LATENCY: Final = "reflex.attempt.latency"
M_ATTEMPT_TTFT: Final = "reflex.attempt.ttft"
M_QUALITY_PASS: Final = "reflex.quality.pass"
M_QUALITY_TOTAL: Final = "reflex.quality.total"
M_RETRY_AMPLIFICATION: Final = "reflex.retry.amplification"
M_COST_USD: Final = "reflex.cost.usd"
M_PROBE_RESULT: Final = "reflex.probe.result"
M_TELEMETRY_DROPPED: Final = "reflex.telemetry.dropped"
M_INCIDENT_OPEN: Final = "reflex.incident.open"
M_CORTEX_DURATION: Final = "reflex.cortex.investigation.duration"
M_CORTEX_TOOL_CALLS: Final = "reflex.cortex.tool.calls"
M_CORTEX_EVIDENCE_INVALID: Final = "reflex.cortex.evidence_invalid"


def base_tags(env: str, route: str | None = None, target: str | None = None) -> list[str]:
    raise NotImplementedError
