"""rps(t) = base · (1 + amplitude · sin(2πt/period)) + noise."""

from __future__ import annotations


def rate_at(t_s: float, base_rps: float, amplitude: float, period_s: float, noise: float) -> float:
    raise NotImplementedError
