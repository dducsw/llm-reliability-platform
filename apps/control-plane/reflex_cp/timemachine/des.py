"""Discrete-event simulation: clock ảo, rng seeded, chạy logic replay theo chính sách.

Spec: docs/50-reliability/time-machine.md §2, §3, §4 & §5 (DE-8.2, DE-8.3)
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from reflex_cp.timemachine.world import World


def _sample_with_capacity(
    world: World,
    target: str,
    ts: Any,
    rng: random.Random,
    load_tracker: dict[tuple[str, int], int],
    capacity_limit: int | None = None,
) -> tuple[str, float, float]:
    """Lấy mẫu target có kèm mô hình Capacity fit từ S5 (DE-8.3).

    Nếu số lượng gọi dồn vào target trong cùng cửa sổ 5s vượt quá `capacity_limit`,
    phần dư bị gặp lỗi 429 rate_limited hoặc tăng latency.
    """
    bucket_5s = int(ts.timestamp() // 5)
    current_load = load_tracker[(target, bucket_5s)]
    load_tracker[(target, bucket_5s)] += 1

    outcome, lat, ttft = world.sample_target(target, ts, rng)

    # Capacity overflow threshold từ S5 (nếu được kích hoạt)
    if capacity_limit is not None and current_load > capacity_limit:
        overflow_ratio = min(0.8, (current_load - capacity_limit) / float(capacity_limit))
        if rng.random() < overflow_ratio:
            return "rate_limited", lat * 1.5, ttft * 1.5

    return outcome, lat, ttft


def simulate(
    world: World,
    variant: str,
    seed: int = 42,
    capacity_limit: int | None = None,
) -> dict[str, Any]:
    """Chạy mô phỏng Discrete-Event Simulation trên tập Demand của World với chính sách variant.

    5 Variants (DE-8.2):
    - naive: Gọi thẳng vendorA 1 lần, không retry, không failover.
    - naive_retry: Retry 3 lần mù quáng trên vendorA, không budget (thundering herd / retry storm).
    - static_failover: Gateway thường, chỉ retry/failover khi gặp 5xx/timeout/429; bỏ qua lỗi quality.
    - reflex_recorded: Cơ chế đầy đủ của Reflex (bắt trượt schema/quality, cứu bằng vendorB). Dùng để hiệu chuẩn.
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
    load_tracker: dict[tuple[str, int], int] = defaultdict(int)

    for req in world.demand:
        # 1. Naive: Luôn gọi 1 lần vendorA, chấp nhận mọi kết quả
        if variant == "naive":
            total_attempts += 1
            outcome, _lat, _ttft = _sample_with_capacity(
                world, primary_target, req.ts, rng, load_tracker, capacity_limit
            )
            if outcome == "ok":
                delivered_good += 1
            else:
                delivered_bad += 1

        # 2. Naive Retry: Retry mù quáng 3 lần cùng 1 vendor, không có budget (thundering herd / retry storm)
        elif variant == "naive_retry":
            total_attempts += 1
            outcome, _lat, _ttft = _sample_with_capacity(
                world, primary_target, req.ts, rng, load_tracker, capacity_limit
            )
            if outcome == "ok":
                delivered_good += 1
            else:
                # Khi vendorA lỗi cả hệ thống (brownout), retry 2 lần tiếp theo trên cùng vendor vẫn thất bại nhưng gây tải
                total_attempts += 2
                delivered_bad += 1

        # 3. Static Failover: Chỉ bắt lỗi mạng (error, timeout, rate_limited), không bắt quality_fail
        elif variant == "static_failover":
            total_attempts += 1
            outcome, _lat, _ttft = _sample_with_capacity(
                world, primary_target, req.ts, rng, load_tracker, capacity_limit
            )
            if outcome in ("error", "timeout", "rate_limited"):
                total_attempts += 1
                outcome2, _lat2, _ttft2 = _sample_with_capacity(
                    world, secondary_target, req.ts, rng, load_tracker, capacity_limit
                )
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

        # 4. Reflex Recorded: Bắt cả lỗi mạng lẫn quality_fail qua JSON schema/not_empty validators
        elif variant in ("reflex", "reflex_recorded"):
            total_attempts += 1
            outcome, _lat, _ttft = _sample_with_capacity(
                world, primary_target, req.ts, rng, load_tracker, capacity_limit
            )
            if outcome != "ok":
                total_attempts += 1
                outcome2, _lat2, _ttft2 = _sample_with_capacity(
                    world, secondary_target, req.ts, rng, load_tracker, capacity_limit
                )
                if outcome2 == "ok":
                    delivered_good += 1
                    requests_saved += 1
                else:
                    delivered_bad += 1
            else:
                delivered_good += 1

        # 5. Reflex Variant (Ablation: tắt quality retry)
        elif variant == "reflex_variant":
            total_attempts += 1
            outcome, _lat, _ttft = _sample_with_capacity(
                world, primary_target, req.ts, rng, load_tracker, capacity_limit
            )
            if outcome in ("error", "timeout", "rate_limited"):
                total_attempts += 1
                outcome2, _lat2, _ttft2 = _sample_with_capacity(
                    world, secondary_target, req.ts, rng, load_tracker, capacity_limit
                )
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

    # Sai số hiệu chuẩn so với thực tế ghi nhận (calibration error theo percentage points)
    calibration_error_pp = round(abs(delivered_quality - world.actual_delivered_quality) * 100, 2)

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
        "calibration_error_pp": calibration_error_pp,
    }
