"""Variants: naive, naive_retry, static_failover, reflex_recorded, reflex_variant (DE-8.2)."""

from __future__ import annotations

VARIANTS = (
    "naive",
    "naive_retry",
    "static_failover",
    "reflex_recorded",
    "reflex_variant",
)

VARIANT_DESCRIPTIONS = {
    "naive": "App gọi thẳng 1 vendor, không retry hay failover",
    "naive_retry": "Retry 3 lần mù quáng trên cùng 1 vendor (thấy rõ retry storm và thundering herd)",
    "static_failover": "Failover khi gặp 5xx/timeout, không kiểm tra schema/quality",
    "reflex_recorded": "Cơ chế đầy đủ của Reflex: Quality rescue, Retry budget, Hedging",
    "reflex_variant": "Ablation: Reflex nhưng tắt cơ chế Quality Retry",
}
