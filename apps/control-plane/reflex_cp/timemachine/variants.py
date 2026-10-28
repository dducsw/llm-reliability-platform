"""Variants: naive (không retry), static_failover (gateway thường), reflex_recorded, reflex_variant."""

from __future__ import annotations

VARIANTS = (
    "naive",
    "static_failover",
    "reflex_recorded",
    "reflex_variant",
)

VARIANT_DESCRIPTIONS = {
    "naive": "App gọi thẳng 1 vendor, không retry hay failover",
    "static_failover": "Failover khi gặp 5xx/timeout, không kiểm tra schema/quality",
    "reflex_recorded": "Cơ chế đầy đủ của Reflex: Quality rescue, Retry budget, Hedging",
    "reflex_variant": "Ablation: Reflex nhưng tắt cơ chế Quality Retry",
}
