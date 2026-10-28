"""ActionSpec catalog + Action state machine + VerificationResult.

Catalog: docs/50-reliability/recovery-engine.md §3. Shape: mongodb-data-model.md §4.7.
"""

from __future__ import annotations

import builtins
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ActionType(StrEnum):
    SHIFT_WEIGHT = "shift_weight"
    OPEN_CIRCUIT_GLOBAL = "open_circuit_global"
    ENABLE_HEDGING = "enable_hedging"
    SET_CONCURRENCY = "set_concurrency"
    SHED_PRIORITY = "shed_priority"
    DOWNGRADE_TIER = "downgrade_tier"
    FAILBACK_STEP = "failback_step"
    ROLLBACK_FLAG = "rollback_flag"
    PAGE_HUMAN = "page_human"


class ActionState(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    AWAITING_APPROVAL = "awaiting_approval"
    REJECTED = "rejected"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class BlastRadius(StrEnum):
    ROUTE = "route"
    TARGET = "target"
    SERVICE = "service"
    NONE = "none"


# --- params schema cho từng action type -------------------------------------


class ShiftWeightParams(_Model):
    route: str
    from_: str = Field(alias="from")
    to: str
    pct: float = Field(gt=0.0, le=1.0)


class OpenCircuitGlobalParams(_Model):
    target: str
    duration_s: int


class EnableHedgingParams(_Model):
    route: str
    after: str = "p95_ttft"
    max_cost: float


class SetConcurrencyParams(_Model):
    route: str | None = None
    target: str | None = None
    limit: int


class ShedPriorityParams(_Model):
    min_priority: int


class DowngradeTierParams(_Model):
    route: str
    to_target: str


class FailbackStepParams(_Model):
    route: str
    to: str
    pct: int  # 10 | 50 | 100


class RollbackFlagParams(_Model):
    flag: str
    service: str


class PageHumanParams(_Model):
    reason: str


class ActionSpec(_Model):
    """Định nghĩa tĩnh của một loại action trong catalog."""

    type: ActionType
    params_model: builtins.type[BaseModel]  # `type` bị field cùng tên che trong class body
    blast_radius: BlastRadius
    reversible: bool
    human_only: bool = False


CATALOG: dict[ActionType, ActionSpec] = {
    ActionType.SHIFT_WEIGHT: ActionSpec(
        type=ActionType.SHIFT_WEIGHT,
        params_model=ShiftWeightParams,
        blast_radius=BlastRadius.ROUTE,
        reversible=True,
    ),
    ActionType.OPEN_CIRCUIT_GLOBAL: ActionSpec(
        type=ActionType.OPEN_CIRCUIT_GLOBAL,
        params_model=OpenCircuitGlobalParams,
        blast_radius=BlastRadius.TARGET,
        reversible=True,
    ),
    ActionType.ENABLE_HEDGING: ActionSpec(
        type=ActionType.ENABLE_HEDGING,
        params_model=EnableHedgingParams,
        blast_radius=BlastRadius.ROUTE,
        reversible=True,
    ),
    ActionType.SET_CONCURRENCY: ActionSpec(
        type=ActionType.SET_CONCURRENCY,
        params_model=SetConcurrencyParams,
        blast_radius=BlastRadius.TARGET,
        reversible=True,
    ),
    ActionType.SHED_PRIORITY: ActionSpec(
        type=ActionType.SHED_PRIORITY,
        params_model=ShedPriorityParams,
        blast_radius=BlastRadius.SERVICE,
        reversible=True,
    ),
    ActionType.DOWNGRADE_TIER: ActionSpec(
        type=ActionType.DOWNGRADE_TIER,
        params_model=DowngradeTierParams,
        blast_radius=BlastRadius.ROUTE,
        reversible=True,
    ),
    ActionType.FAILBACK_STEP: ActionSpec(
        type=ActionType.FAILBACK_STEP,
        params_model=FailbackStepParams,
        blast_radius=BlastRadius.ROUTE,
        reversible=True,
    ),
    ActionType.ROLLBACK_FLAG: ActionSpec(
        type=ActionType.ROLLBACK_FLAG,
        params_model=RollbackFlagParams,
        blast_radius=BlastRadius.SERVICE,
        reversible=True,
    ),
    ActionType.PAGE_HUMAN: ActionSpec(
        type=ActionType.PAGE_HUMAN,
        params_model=PageHumanParams,
        blast_radius=BlastRadius.NONE,
        reversible=False,
        human_only=True,
    ),
}


# --- runtime document --------------------------------------------------------


class GuardrailResult(_Model):
    name: str
    pass_: bool = Field(alias="pass")
    detail: str | None = None


class Decision(_Model):
    mode: str  # auto | human
    by: str
    at: datetime
    guardrails: list[GuardrailResult] = []


class Execution(_Model):
    policy_id: str
    version_before: int
    version_after: int
    applied_at: datetime


class Proportion(_Model):
    good: int
    n: int


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class VerificationResult(_Model):
    window: dict[str, tuple[datetime, datetime]]  # {baseline, after}
    metric: str
    baseline: Proportion
    after: Proportion
    method: str = "wilson+two_proportion"
    after_ci: tuple[float, float]
    p_value: float
    verdict: Verdict
    decided_at: datetime


class ProposedBy(_Model):
    actor: str  # cortex | human | rules
    investigation_id: str | None = None
    confidence: float | None = None  # cortex/rules; guardrail `confidence` đọc trường này


class Action(_Model):
    id: str | None = Field(default=None, alias="_id")
    incident_id: str | None = None
    parent_action_id: str | None = None
    type: ActionType
    params: dict[str, Any]
    state: ActionState = ActionState.PROPOSED
    proposed_by: ProposedBy
    decision: Decision | None = None
    execution: Execution | None = None
    verification: VerificationResult | None = None
    ttr_s: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


TRANSITIONS: dict[ActionState, set[ActionState]] = {
    ActionState.PROPOSED: {
        ActionState.APPROVED,
        ActionState.AWAITING_APPROVAL,
        ActionState.REJECTED,
    },
    ActionState.AWAITING_APPROVAL: {ActionState.APPROVED, ActionState.REJECTED},
    ActionState.APPROVED: {ActionState.EXECUTING, ActionState.REJECTED},
    ActionState.EXECUTING: {ActionState.VERIFYING, ActionState.SUCCEEDED, ActionState.FAILED},
    ActionState.VERIFYING: {ActionState.SUCCEEDED, ActionState.FAILED, ActionState.ROLLED_BACK},
    ActionState.SUCCEEDED: {ActionState.ROLLED_BACK},
    ActionState.FAILED: {ActionState.ROLLED_BACK},
    ActionState.REJECTED: set(),
    ActionState.ROLLED_BACK: set(),
}


def can_transition(src: ActionState, dst: ActionState) -> bool:
    return dst in TRANSITIONS.get(src, set())


def validate_params(action_type: ActionType, params: dict[str, Any]) -> BaseModel:
    spec = CATALOG.get(action_type)
    if spec is None:
        raise ValueError(f"Unknown action type: {action_type}")
    return spec.params_model.model_validate(params)
