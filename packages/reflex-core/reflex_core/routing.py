"""Router: eligibility → scoring → softmax sampling. Clock/RNG được inject.

Công thức: docs/50-reliability/recovery-engine.md §1.
score(t) = w_h·H + w_b·B + w_q·Q − w_c·C + w_k·K, rồi nhân weight_policy, softmax(temperature).
"""

from __future__ import annotations

from dataclasses import dataclass

from reflex_core.ids import Rng
from reflex_core.policy import Candidate, Policy


@dataclass(frozen=True, slots=True)
class TargetInputs:
    target: str
    health: float  # H(t)
    budget_headroom: float  # B(t)
    quality: float  # Q(t)
    cost: float  # C(t), đã chuẩn hóa [0,1]
    capacity: float  # K(t)
    breaker_open: bool
    eligible: bool = True


@dataclass(frozen=True, slots=True)
class RouteDecision:
    ordered: list[str]  # thứ tự thử: primary, rồi fallback
    probabilities: dict[str, float]
    scores: dict[str, float]


def eligible(candidate: Candidate, inputs: TargetInputs) -> bool:
    raise NotImplementedError


def score(policy: Policy, inputs: TargetInputs) -> float:
    raise NotImplementedError


def softmax(scores: dict[str, float], temperature: float) -> dict[str, float]:
    raise NotImplementedError


def decide(policy: Policy, inputs: dict[str, TargetInputs], rng: Rng) -> RouteDecision:
    raise NotImplementedError
