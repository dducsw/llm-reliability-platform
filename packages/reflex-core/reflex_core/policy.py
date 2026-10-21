"""Policy schema (một policy cho mỗi route) + defaults + diff.

Shape khớp docs/30-data/mongodb-data-model.md §4.3. `version` dùng optimistic concurrency.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CandidateRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    BROWNOUT = "brownout"


class Candidate(_Model):
    target: str
    weight: float = Field(ge=0.0, le=1.0)
    role: CandidateRole


class Scoring(_Model):
    w_health: float = 0.35
    w_budget: float = 0.25
    w_cost: float = 0.15
    w_quality: float = 0.20
    w_capacity: float = 0.05
    temperature: float = 0.15


class BreakerConfig(_Model):
    window_s: int = 20
    min_requests: int = 20
    open_error_ratio: float = 0.5
    open_base_s: int = 10
    open_max_s: int = 120
    half_open_probes: int = 3


class RetryConfig(_Model):
    max_attempts: int = 3
    budget_ratio: float = 0.10
    on: list[str] = ["5xx", "timeout", "rate_limited"]
    respect_retry_after: bool = True


class RescueConfig(_Model):
    enabled: bool = True
    on: list[str] = ["quality"]
    cross_target_only: bool = True
    max_extra_cost_ratio: float = 0.6


class HedgeConfig(_Model):
    enabled: bool = False
    after: str = "p95_ttft"
    max_extra_cost_ratio: float = 0.05


class ShedConfig(_Model):
    when_all_degraded_min_priority: int = 1


class UpdatedBy(_Model):
    actor: str
    action_id: str | None = None
    reason: str | None = None


class Policy(_Model):
    id: str = Field(alias="_id")  # route name
    version: int
    candidates: list[Candidate]
    scoring: Scoring = Scoring()
    breaker: BreakerConfig = BreakerConfig()
    retry: RetryConfig = RetryConfig()
    rescue: RescueConfig = RescueConfig()
    hedge: HedgeConfig = HedgeConfig()
    validators: list[str] = []
    deadline_ms: int = 8000
    shed: ShedConfig = ShedConfig()
    updated_by: UpdatedBy | None = None
    updated_at: datetime | None = None


def default_policy(route: str, candidates: list[Candidate]) -> Policy:
    raise NotImplementedError


def diff(before: Policy, after: Policy) -> dict[str, Any]:
    """Diff có cấu trúc để hiển thị trên Console (Approvals, Policies)."""
    raise NotImplementedError


def validate_policy(policy: Policy) -> list[str]:
    """Kiểm tra bất biến (tổng weight, target tồn tại…) trước khi gateway hot-reload."""
    raise NotImplementedError
