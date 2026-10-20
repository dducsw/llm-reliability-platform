"""Mergeable histogram 20 bucket log-scale (mongodb-data-model.md §3.3)."""

from __future__ import annotations

BOUNDS_MS: tuple[float, ...] = (
    50, 100, 150, 200, 300, 400, 500, 750, 1000, 1500,
    2000, 3000, 4000, 6000, 8000, 12000, 16000, 24000, 32000,
)  # fmt: skip
"""19 biên hữu hạn; bucket thứ 20 là (32000, ∞)."""

NB = len(BOUNDS_MS) + 1


def bucket_index(value_ms: float) -> int:
    raise NotImplementedError


def empty() -> list[int]:
    raise NotImplementedError


def observe(hist: list[int], value_ms: float) -> None:
    raise NotImplementedError


def merge(a: list[int], b: list[int]) -> list[int]:
    raise NotImplementedError


def quantile(hist: list[int], q: float) -> float:
    """Nội suy tuyến tính trong bucket chứa quantile."""
    raise NotImplementedError


def count_le(hist: list[int], threshold_ms: float) -> int:
    """Chính xác khi threshold trùng một biên bucket (bắt buộc với SLO latency)."""
    raise NotImplementedError
