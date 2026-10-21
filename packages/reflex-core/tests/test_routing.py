import math
import pytest
from reflex_core.policy import Candidate, CandidateRole, Policy
from reflex_core.routing import TargetInputs, decide, eligible, score, softmax


class DeterministicRng:
    def __init__(self, val: float = 0.1) -> None:
        self.val = val

    def random(self) -> float:
        return self.val

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.val


def test_eligible_filter() -> None:
    cand = Candidate(target="vendorA:large", weight=0.8, role=CandidateRole.PRIMARY)
    inp_ok = TargetInputs(
        target="vendorA:large",
        health=1.0,
        budget_headroom=1.0,
        quality=1.0,
        cost=0.5,
        capacity=1.0,
        breaker_open=False,
        eligible=True,
    )
    assert eligible(cand, inp_ok) is True

    inp_breaker = TargetInputs(
        target="vendorA:large",
        health=0.0,
        budget_headroom=1.0,
        quality=1.0,
        cost=0.5,
        capacity=1.0,
        breaker_open=True,
        eligible=True,
    )
    assert eligible(cand, inp_breaker) is False


def test_softmax_probabilities_sum_to_one() -> None:
    scores = {"target1": 1.5, "target2": 0.8, "target3": -0.2}
    probs = softmax(scores, temperature=0.2)
    assert math.isclose(sum(probs.values()), 1.0, rel_tol=1e-5)
    assert probs["target1"] > probs["target2"] > probs["target3"]


def test_decide_routing() -> None:
    policy = Policy(
        _id="order.extract",
        version=1,
        candidates=[
            Candidate(target="vendorA:large", weight=0.7, role=CandidateRole.PRIMARY),
            Candidate(target="vendorB:fallback", weight=0.3, role=CandidateRole.SECONDARY),
        ],
    )
    inputs = {
        "vendorA:large": TargetInputs(
            target="vendorA:large",
            health=1.0,
            budget_headroom=1.0,
            quality=1.0,
            cost=0.5,
            capacity=1.0,
            breaker_open=False,
        ),
        "vendorB:fallback": TargetInputs(
            target="vendorB:fallback",
            health=1.0,
            budget_headroom=1.0,
            quality=1.0,
            cost=0.5,
            capacity=1.0,
            breaker_open=False,
        ),
    }

    decision = decide(policy, inputs, DeterministicRng(0.1))
    assert len(decision.ordered) == 2
    assert "vendorA:large" in decision.probabilities
    assert "vendorB:fallback" in decision.probabilities
    assert math.isclose(sum(decision.probabilities.values()), 1.0, rel_tol=1e-5)
