"""Telemetry events — contract giữa gateway/prober (ghi) và control-plane/cortex (đọc).

Shape khớp docs/30-data/mongodb-data-model.md §2. Thay đổi phải tăng `v`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)


class RequestOutcome(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    QUALITY_FAIL = "quality_fail"
    SHED = "shed"
    DEADLINE = "deadline"


class AttemptKind(StrEnum):
    PRIMARY = "primary"
    RETRY = "retry"
    QUALITY_RETRY = "quality_retry"
    HEDGE = "hedge"
    PROBE = "probe"


class AttemptOutcome(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    QUALITY_FAIL = "quality_fail"
    CANCELLED = "cancelled"


class ProbePath(StrEnum):
    DIRECT = "direct"
    VIA_GATEWAY = "via_gateway"


class RequestMeta(_Model):
    route: str
    env: str
    synthetic: bool = False


class AttemptMeta(_Model):
    target: str
    env: str
    synthetic: bool = False


class ProbeMeta(_Model):
    target: str
    path: ProbePath
    env: str


class QualityResult(_Model):
    pass_: bool = Field(alias="pass")
    checks: list[str] = []
    failed: list[str] = []
    truncated: bool = False


class RequestEvent(_Model):
    """Một document `requests_ts` cho mỗi request client (Delivered ledger)."""

    ts: datetime
    meta: RequestMeta
    v: int = 1
    request_id: str
    trace_id: str | None = None
    session: str | None = None
    priority: int = 1
    outcome: RequestOutcome
    final_target: str | None = None
    primary_target: str | None = None
    attempts: int = 1
    hedged: bool = False
    retry_reasons: list[str] = []
    latency_ms: float
    ttft_ms: float | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    quality: QualityResult | None = None
    policy_version: int
    incident_id: str | None = None


class AttemptEvent(_Model):
    """Một document `attempts_ts` cho mỗi lần gọi upstream (Provider ledger)."""

    ts: datetime
    meta: AttemptMeta
    v: int = 1
    request_id: str
    trace_id: str | None = None
    span_id: str | None = None
    route: str
    attempt_no: int
    kind: AttemptKind
    outcome: AttemptOutcome
    http_status: int | None = None
    error_class: str | None = None
    finish_reason: str | None = None
    latency_ms: float
    ttft_ms: float | None = None
    tps: float | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    quality: QualityResult | None = None
    cost_usd: float = 0.0
    gateway_id: str
    breaker_state: str


class ProbeEvent(_Model):
    """Một document `probes_ts` — golden prompt canary mỗi 15s."""

    ts: datetime
    meta: ProbeMeta
    v: int = 1
    golden_id: str
    outcome: AttemptOutcome
    latency_ms: float
    ttft_ms: float | None = None
    quality: QualityResult | None = None
    http_status: int | None = None


class BenchEvent(_Model):
    """Một document `bench_ts` — import từ Jwrede/llm-bench-data."""

    ts: datetime
    meta: dict[str, str]  # {model, vendor, source}
    status: str
    ttft_ms: float | None = None
    latency_ms: float | None = None
    tps: float | None = None
    token_count: int | None = None
