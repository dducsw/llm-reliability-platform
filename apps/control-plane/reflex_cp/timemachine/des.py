"""Discrete-event simulation: clock ảo, rng seeded, chạy logic replay theo chính sách.

Spec: docs/50-reliability/time-machine.md §2 & §5
"""

from __future__ import annotations

import random
from typing import Any

from reflex_cp.timemachine.world import World


def simulate(world: World, variant: str, seed: int = 42) -> dict[str, Any]:
    """Chạy mô phỏng Discrete-Event Simulation trên tập Demand của World với chính sách variant.

    Variants:
    - naive: Gọi thẳng vendorA, không retry, không failover.
    - static_failover: Gateway thường, chỉ retry/failover khi gặp lỗi mạng/5xx; bỏ qua lỗi quality.
    - reflex_recorded: Cơ chế đầy đủ của Reflex (bắt trượt schema/quality, cứu bằng vendorB).
    - reflex_variant: Reflex nhưng tắt cơ chế Quality Retry để đo ablation.
    """
    rng = random.Random(seed)
    primary_target = "vendorA:large"
    secondary_target = "vendorB:fallback"

    total_requests = len(world.demand)
    delivered_good = 0
    delivered_bad = 0
    total_attempts = 0
    requests_saved = 0

    base_cost_per_attempt = 0.0023

    for req in world.demand:
        # 1. Naive: Luôn gọi 1 lần vendorA, chấp nhận mọi kết quả
        if variant == "naive":
            total_attempts += 1
            outcome, _lat, _ttft = world.sample_target(primary_target, req.ts, rng)
            if outcome == "ok":
                delivered_good += 1
            else:
                delivered_bad += 1

        # 2. Static Failover: Chỉ bắt lỗi mạng (error, timeout, rate_limited), không bắt quality_fail
        elif variant == "static_failover":
            total_attempts += 1
            outcome, _lat, _ttft = world.sample_target(primary_target, req.ts, rng)
            if outcome in ("error", "timeout", "rate_limited"):
                total_attempts += 1
                outcome2, _lat2, _ttft2 = world.sample_target(secondary_target, req.ts, rng)
                if outcome2 == "ok":
                    delivered_good += 1
                    requests_saved += 1
                else:
                    delivered_bad += 1
            elif outcome == "ok":
                delivered_good += 1
            else:
                # quality_fail lọt qua người dùng vì gateway không có validator
                delivered_bad += 1

        # 3. Reflex Recorded: Bắt cả lỗi mạng lẫn quality_fail qua JSON schema/not_empty validators
        elif variant in ("reflex", "reflex_recorded"):
            total_attempts += 1
            outcome, _lat, _ttft = world.sample_target(primary_target, req.ts, rng)
            if outcome != "ok":
                total_attempts += 1
                outcome2, _lat2, _ttft2 = world.sample_target(secondary_target, req.ts, rng)
                if outcome2 == "ok":
                    delivered_good += 1
                    requests_saved += 1
                else:
                    delivered_bad += 1
            else:
                delivered_good += 1

        # 4. Reflex Variant (Ablation: tắt quality retry)
        elif variant == "reflex_variant":
            total_attempts += 1
            outcome, _lat, _ttft = world.sample_target(primary_target, req.ts, rng)
            if outcome in ("error", "timeout", "rate_limited"):
                total_attempts += 1
                outcome2, _lat2, _ttft2 = world.sample_target(secondary_target, req.ts, rng)
                if outcome2 == "ok":
                    delivered_good += 1
                    requests_saved += 1
                else:
                    delivered_bad += 1
            elif outcome == "ok":
                delivered_good += 1
            else:
                delivered_bad += 1

        else:
            total_attempts += 1
            delivered_good += 1

    extra_attempts = max(0, total_attempts - total_requests)
    extra_cost_usd = round(extra_attempts * base_cost_per_attempt, 2)
    delivered_quality = round(delivered_good / max(1, total_requests), 4)

    # Giả định Error Budget là 1.0% (objective 99.0%)
    allowed_bad = max(1, total_requests * 0.01)
    budget_consumed = round(min(1.0, delivered_bad / allowed_bad), 4)

    return {
        "variant": variant,
        "seed": seed,
        "total_requests": total_requests,
        "delivered_good": delivered_good,
        "delivered_bad": delivered_bad,
        "delivered_quality": delivered_quality,
        "budget_consumed": budget_consumed,
        "extra_cost_usd": extra_cost_usd,
        "attempts_per_request": round(total_attempts / max(1, total_requests), 2),
        "requests_saved": requests_saved,
    }
