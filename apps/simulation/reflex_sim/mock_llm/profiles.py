"""Profile latency (log-normal TTFT, tps) — prior lấy từ bench_ts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatencyProfile:
    ttft_mu: float
    ttft_sigma: float
    tps_mean: float
    tps_std: float
