"""Mergeable histogram 20 bucket log-scale (mongodb-data-model.md §3.3)."""

from __future__ import annotations

import bisect

BOUNDS_MS: tuple[float, ...] = (
    50, 100, 150, 200, 300, 400, 500, 750, 1000, 1500,
    2000, 3000, 4000, 6000, 8000, 12000, 16000, 24000, 32000,
)  # fmt: skip
"""19 biên hữu hạn; bucket thứ 20 là (32000, ∞)."""

NB = len(BOUNDS_MS) + 1


def bucket_index(value_ms: float) -> int:
    """Chỉ số bucket từ 0 đến NB - 1 (19)."""
    return bisect.bisect_left(BOUNDS_MS, value_ms)


def empty() -> list[int]:
    """Khởi tạo mảng 20 bucket số 0."""
    return [0] * NB


def observe(hist: list[int], value_ms: float) -> None:
    """Tăng đếm cho bucket chứa value_ms."""
    idx = bucket_index(value_ms)
    hist[idx] += 1


def merge(a: list[int], b: list[int]) -> list[int]:
    """Cộng dồn hai vector histogram."""
    return [x + y for x, y in zip(a, b, strict=True)]


def quantile(hist: list[int], q: float) -> float:
    """Nội suy tuyến tính trong bucket chứa quantile (0.0 <= q <= 1.0)."""
    total = sum(hist)
    if total == 0:
        return 0.0
    q = max(0.0, min(1.0, q))
    target = q * total

    cumulative = 0
    for i in range(NB):
        count = hist[i]
        if cumulative + count >= target:
            lower = 0.0 if i == 0 else BOUNDS_MS[i - 1]
            upper = BOUNDS_MS[i] if i < len(BOUNDS_MS) else BOUNDS_MS[-1] * 1.5
            if count == 0:
                return lower
            fraction = (target - cumulative) / count
            return lower + fraction * (upper - lower)
        cumulative += count
    return float(BOUNDS_MS[-1])


def count_le(hist: list[int], threshold_ms: float) -> int:
    """Chính xác khi threshold trùng một biên bucket (bắt buộc với SLO latency)."""
    idx = bisect.bisect_right(BOUNDS_MS, threshold_ms) - 1
    if idx < 0:
        return 0
    return sum(hist[: idx + 1])
