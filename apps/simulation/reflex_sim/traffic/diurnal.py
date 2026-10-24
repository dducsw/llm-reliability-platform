"""rps(t) = base · (1 + amplitude · sin(2πt/period)) + noise."""

from __future__ import annotations

import math


def rate_at(
    t_s: float, base_rps: float, amplitude: float, period_s: float, noise: float = 0.0
) -> float:
    """Tính rps tại thời điểm t_s với chu kỳ ngày đêm hình sin."""
    if period_s <= 0:
        return max(0.1, base_rps + noise)
    factor = 1.0 + amplitude * math.sin(2.0 * math.pi * t_s / period_s)
    return max(0.1, base_rps * factor + noise)
