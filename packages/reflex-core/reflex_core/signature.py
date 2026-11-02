"""Incident signature 64 chiều: 16 bước (−12m…+3m) × 4 kênh
(err_ratio, quality_fail_ratio, latency_dev, ttft_dev). Dùng chung với A9.

Layout theo kênh (channel-major), khớp `$concatArrays` của A9:
`[err_ratio×16, quality_fail_ratio×16, latency_dev×16, ttft_dev×16]`.
"""

from __future__ import annotations

import math

STEPS = 16
CHANNELS = ("err_ratio", "quality_fail_ratio", "latency_dev", "ttft_dev")
DIM = STEPS * len(CHANNELS)


def build(series: dict[str, list[float]]) -> list[float]:
    """Ghép 4 kênh × 16 bước thành vector 64 chiều. Kênh thiếu → 0 (không tín hiệu)."""
    vec: list[float] = []
    for channel in CHANNELS:
        values = series.get(channel, [0.0] * STEPS)
        if len(values) != STEPS:
            raise ValueError(f"kênh {channel} cần {STEPS} bước, nhận {len(values)}")
        vec.extend(float(v) for v in values)
    return vec


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity như `$vectorSearch` (A10); vector 0 → 0.0 thay vì chia cho 0."""
    if len(a) != len(b):
        raise ValueError(f"lệch số chiều: {len(a)} vs {len(b)}")
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if norm == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm
