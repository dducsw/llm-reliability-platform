"""Profile latency (log-normal TTFT, tps) — prior lấy từ bench_ts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatencyProfile:
    ttft_mu: float
    ttft_sigma: float
    tps_mean: float
    tps_std: float


PROFILES: dict[str, LatencyProfile] = {
    "large": LatencyProfile(ttft_mu=5.5, ttft_sigma=0.3, tps_mean=60.0, tps_std=5.0),
    "small": LatencyProfile(ttft_mu=4.8, ttft_sigma=0.2, tps_mean=80.0, tps_std=8.0),
    "mock": LatencyProfile(ttft_mu=4.5, ttft_sigma=0.1, tps_mean=100.0, tps_std=10.0),
}


def get_profile(name: str) -> LatencyProfile:
    return PROFILES.get(name, PROFILES["large"])
