"""Unit tests cho reflex_core.policy."""

from reflex_core.policy import (
    Candidate,
    CandidateRole,
    Policy,
    default_policy,
    diff,
    validate_policy,
)


def test_default_policy() -> None:
    cands = [
        Candidate(target="vendorA:large", weight=0.9, role=CandidateRole.PRIMARY),
        Candidate(target="vendorB:large", weight=0.1, role=CandidateRole.SECONDARY),
    ]
    p = default_policy("order.extract", cands)
    assert p.id == "order.extract"
    assert p.version == 1
    assert len(p.candidates) == 2
    assert validate_policy(p) == []


def test_diff_policies() -> None:
    cands1 = [Candidate(target="vendorA:large", weight=0.9, role=CandidateRole.PRIMARY)]
    cands2 = [Candidate(target="vendorA:large", weight=0.5, role=CandidateRole.PRIMARY)]
    p1 = default_policy("chat", cands1)
    p2 = Policy(id="chat", version=2, candidates=cands2, deadline_ms=5000)

    d = diff(p1, p2)
    assert d["version"] == {"before": 1, "after": 2}
    assert d["deadline_ms"] == {"before": 8000, "after": 5000}
    assert "weights" in d
