"""Thống kê cho Recovery Proof: Wilson score interval, two-proportion z-test."""

from __future__ import annotations

import math

from scipy import stats


def wilson_interval(good: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval cho tỉ lệ nhị thức."""
    if n <= 0:
        return 0.0, 1.0
    if good >= n:
        p = 1.0
        z = stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
        ci_low = max(
            0.0,
            float(
                (1.0 + (z**2) / (2.0 * n) - z * math.sqrt((z**2) / (4.0 * n * n)))
                / (1.0 + (z**2) / n)
            ),
        )
        return ci_low, 1.0
    if good <= 0:
        p = 0.0
        z = stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
        ci_high = min(
            1.0,
            float(
                ((z**2) / (2.0 * n) + z * math.sqrt((z**2) / (4.0 * n * n))) / (1.0 + (z**2) / n)
            ),
        )
        return 0.0, ci_high

    p = good / n
    z = stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
    denominator = 1.0 + (z**2) / n
    center = p + (z**2) / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p) + (z**2) / (4.0 * n)) / n)
    ci_low = max(0.0, float((center - margin) / denominator))
    ci_high = min(1.0, float((center + margin) / denominator))
    return ci_low, ci_high


def two_proportion_z(good_a: int, n_a: int, good_b: int, n_b: int) -> tuple[float, float]:
    """Trả về (z, p_value) một phía: H1 là tỉ lệ b > a."""
    if n_a <= 0 or n_b <= 0:
        return 0.0, 1.0
    p_a = good_a / n_a
    p_b = good_b / n_b
    pooled = (good_a + good_b) / (n_a + n_b)
    if pooled <= 0.0 or pooled >= 1.0:
        return 0.0, 1.0 if p_b <= p_a else 0.0
    se = math.sqrt(pooled * (1.0 - pooled) * (1.0 / n_a + 1.0 / n_b))
    if se <= 0.0:
        return 0.0, 1.0
    z = (p_b - p_a) / se
    p_val = 1.0 - float(stats.norm.cdf(z))
    return float(z), float(p_val)


def min_samples(objective: float, confidence: float = 0.95) -> int:
    """Cỡ mẫu tối thiểu cho kiểm định (docs/50-reliability/recovery-engine.md §5: n >= 200)."""
    return 200
