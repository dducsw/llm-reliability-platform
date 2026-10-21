"""Incident, Signal, Investigation — shape theo mongodb-data-model.md §4.5–4.6."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class IncidentStatus(StrEnum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"


class Side(StrEnum):
    PROVIDER = "provider"
    GATEWAY = "gateway"
    UNKNOWN = "unknown"


class Signal(_Model):
    source: str  # sentinel | datadog | human
    at: datetime
    burn: dict[str, float] | None = None
    monitor_id: int | None = None
    alert_id: str | None = None
    diagnosis: str | None = None


class IncidentTimes(_Model):
    first_bad_at: datetime | None = None
    detected_at: datetime | None = None
    acknowledged_at: datetime | None = None
    mitigated_at: datetime | None = None
    resolved_at: datetime | None = None


class Impact(_Model):
    requests: int = 0
    sessions: int = 0
    delivered_bad: int = 0
    budget_consumed: float = 0.0
    extra_cost_usd: float = 0.0


class Diagnosis(_Model):
    side: Side
    hypothesis: str
    confidence: float
    by: str
    investigation_id: str | None = None


class Signature(_Model):
    v: int = 2
    vec: list[float]  # 64 chiều: 16 bước × 4 kênh
    window: dict[str, datetime]


class TimelineEntry(_Model):
    at: datetime
    kind: str
    actor: str
    ref: str | None = None


class Incident(_Model):
    id: str | None = Field(default=None, alias="_id")
    key: str
    dedup_key: str
    is_open: bool | None = True
    slo_id: str
    scope: str
    target: str | None = None
    routes: list[str] = []
    sli: str
    severity: Severity
    status: IncidentStatus = IncidentStatus.DETECTED
    signals: list[Signal] = []
    t: IncidentTimes = IncidentTimes()
    impact: Impact | None = None
    diagnosis: Diagnosis | None = None
    signature: Signature | None = None
    links: dict[str, str] = {}
    timeline: list[TimelineEntry] = []
    postmortem_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InvestigationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ToolStep(_Model):
    n: int
    tool: str
    args: dict[str, Any]
    ms: float
    result_digest: str | None = None
    result_ref: str | None = None


class Evidence(_Model):
    type: str  # metric | log | trace | memory | probe
    ref: str
    claim: str


class Hypothesis(_Model):
    id: str
    statement: str
    confidence: float
    evidence: list[Evidence] = []


class Recommendation(_Model):
    action_type: str
    params: dict[str, Any]
    expected_effect: dict[str, str] = {}


class Investigation(_Model):
    id: str | None = Field(default=None, alias="_id")
    incident_id: str
    run_no: int = 1
    status: InvestigationStatus = InvestigationStatus.RUNNING
    model: str | None = None
    via_gateway_route: str = "cortex.reason"
    context_pack_ref: dict[str, Any] = {}
    steps: list[ToolStep] = []
    hypotheses: list[Hypothesis] = []
    recommendation: Recommendation | None = None
    usage: dict[str, float] = {}
    dd: dict[str, str] = {}
