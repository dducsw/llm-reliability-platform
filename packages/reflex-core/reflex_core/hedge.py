"""Hedging: bắn attempt song song khi primary vượt p95 TTFT, giới hạn bằng chi phí."""

from __future__ import annotations

from reflex_core.policy import HedgeConfig


def hedge_delay_ms(config: HedgeConfig, ttft_p95_ms: float | None) -> float | None:
    if not config.enabled:
        return None
    if ttft_p95_ms is None or ttft_p95_ms <= 0:
        return None
    return float(ttft_p95_ms)


def should_hedge(config: HedgeConfig, spent_ratio: float) -> bool:
    if not config.enabled:
        return False
    return spent_ratio <= config.max_extra_cost_ratio
