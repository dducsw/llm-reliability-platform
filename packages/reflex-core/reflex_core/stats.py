"""Thống kê cho Recovery Proof: Wilson score interval, two-proportion z-test."""

from __future__ import annotations


def wilson_interval(good: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    raise NotImplementedError


def two_proportion_z(good_a: int, n_a: int, good_b: int, n_b: int) -> tuple[float, float]:
    """Trả về (z, p_value) một phía: H1 là tỉ lệ b > a."""
    raise NotImplementedError


def min_samples(objective: float, confidence: float = 0.95) -> int:
    raise NotImplementedError
