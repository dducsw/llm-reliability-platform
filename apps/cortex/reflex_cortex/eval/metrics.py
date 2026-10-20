from __future__ import annotations


def score(prediction: dict, ground_truth: dict) -> dict[str, float]:
    """side_acc, cause_acc, action_acc, evidence_valid, cost, latency."""
    raise NotImplementedError
