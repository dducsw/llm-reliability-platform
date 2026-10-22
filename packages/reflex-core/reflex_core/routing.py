"""Router: eligibility → scoring → softmax sampling. Clock/RNG được inject.

Công thức: docs/50-reliability/recovery-engine.md §1.
score(t) = w_h·H + w_b·B + w_q·Q + w_c·(1 − C) + w_k·K + log(weight_policy), softmax(temperature).
"""

from __future__ import annotations

import math
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
    if not inputs.eligible:
        return False
    if inputs.breaker_open:
        return False
    return True


def score(policy: Policy, inputs: TargetInputs) -> float:
    sc = policy.scoring
    raw_score = (
        sc.w_health * inputs.health
        + sc.w_budget * inputs.budget_headroom
        + sc.w_quality * inputs.quality
        + sc.w_cost * (1.0 - inputs.cost)
        + sc.w_capacity * inputs.capacity
    )

    cand = next((c for c in policy.candidates if c.target == inputs.target), None)
    w_policy = cand.weight if cand and cand.weight > 0 else 1e-4
    return raw_score + math.log(w_policy)


def softmax(scores: dict[str, float], temperature: float = 0.15) -> dict[str, float]:
    if not scores:
        return {}
    temp = max(temperature, 1e-4)
    max_val = max(scores.values())
    exp_vals = {k: math.exp((v - max_val) / temp) for k, v in scores.items()}
    total = sum(exp_vals.values())
    if total == 0:
        n = len(scores)
        return {k: 1.0 / n for k in scores}
    return {k: v / total for k, v in exp_vals.items()}


def decide(policy: Policy, inputs: dict[str, TargetInputs], rng: Rng) -> RouteDecision:
    # 1. Eligibility filter
    eligible_cands = [
        c for c in policy.candidates if c.target in inputs and eligible(c, inputs[c.target])
    ]

    # Nếu không có target nào eligible, fallback dùng toàn bộ candidate có sẵn
    if not eligible_cands:
        eligible_cands = [c for c in policy.candidates if c.target in inputs]
    if not eligible_cands:
        return RouteDecision(ordered=[], probabilities={}, scores={})

    # 2. Score
    scores = {c.target: score(policy, inputs[c.target]) for c in eligible_cands}

    # 3. Softmax probabilities
    probs = softmax(scores, temperature=policy.scoring.temperature)

    # 4. Sampling primary target theo CDF
    r = rng.random()
    cum = 0.0
    primary = eligible_cands[0].target
    for target, p in probs.items():
        cum += p
        if r <= cum:
            primary = target
            break

    # 5. Order: primary đầu tiên, các target còn lại xếp theo điểm số giảm dần
    fallbacks = sorted(
        [t for t in scores if t != primary],
        key=lambda t: scores[t],
        reverse=True,
    )
    ordered = [primary, *fallbacks]

    return RouteDecision(
        ordered=ordered,
        probabilities=probs,
        scores=scores,
    )
