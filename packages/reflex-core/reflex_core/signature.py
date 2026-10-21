"""Incident signature 64 chiều: 16 bước (−12m…+3m) × 4 kênh
(err_ratio, quality_fail_ratio, latency_dev, ttft_dev). Dùng chung với A9."""

from __future__ import annotations

STEPS = 16
CHANNELS = ("err_ratio", "quality_fail_ratio", "latency_dev", "ttft_dev")
DIM = STEPS * len(CHANNELS)


def build(series: dict[str, list[float]]) -> list[float]:
    raise NotImplementedError


def cosine(a: list[float], b: list[float]) -> float:
    raise NotImplementedError
