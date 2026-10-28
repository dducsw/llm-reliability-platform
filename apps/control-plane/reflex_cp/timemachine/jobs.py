"""Xử lý job Time Machine Monte Carlo counterfactual replay.

Spec: docs/50-reliability/time-machine.md §3 & §5
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import REPLAYS

from reflex_cp.timemachine.des import simulate
from reflex_cp.timemachine.variants import VARIANT_DESCRIPTIONS, VARIANTS
from reflex_cp.timemachine.world import World

logger = logging.getLogger(__name__)


def _calc_stats(values: list[float]) -> dict[str, float]:
    """Tính mean, std và khoảng tin cậy 90% (1.645 * std / sqrt(n))."""
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "std": 0.0, "ci_90_margin": 0.0}
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / max(1, n - 1)
    std = math.sqrt(variance)
    ci_margin = 1.645 * (std / math.sqrt(n))
    return {
        "mean": round(mean, 4),
        "std": round(std, 4),
        "ci_90_margin": round(ci_margin, 4),
    }


async def run_replay(
    incident_key: str,
    variants: list[str] | None = None,
    k: int = 20,
    seed: int = 42,
    db: AsyncDatabase | None = None,
    replay_id: str | None = None,
) -> dict[str, Any]:
    """Chạy Monte Carlo K lần cho mỗi variant, tính hiệu chuẩn và lưu vào collection replays."""
    now = datetime.now(tz=UTC)
    replay_id = replay_id or f"rp-{uuid.uuid4().hex[:10]}"
    target_variants = variants or list(VARIANTS)

    # 1. Dựng World Model (Demand + Target slices)
    world = await World.load(incident_key, db=db)

    # 2. Chạy mô phỏng K seeds
    variant_results: dict[str, Any] = {}
    reflex_mean_quality = 0.994

    for var in target_variants:
        runs = []
        for i in range(k):
            run_res = simulate(world, var, seed=seed + i)
            runs.append(run_res)

        qualities = [r["delivered_quality"] for r in runs]
        budgets = [r["budget_consumed"] for r in runs]
        costs = [r["extra_cost_usd"] for r in runs]
        attempts = [r["attempts_per_request"] for r in runs]
        saved = [r["requests_saved"] for r in runs]

        q_stats = _calc_stats(qualities)
        if var in ("reflex", "reflex_recorded"):
            reflex_mean_quality = q_stats["mean"]

        variant_results[var] = {
            "description": VARIANT_DESCRIPTIONS.get(var, var),
            "delivered_quality": q_stats["mean"],
            "quality_ci_90": q_stats["ci_90_margin"],
            "budget_consumed": _calc_stats(budgets)["mean"],
            "extra_cost_usd": _calc_stats(costs)["mean"],
            "attempts_per_request": _calc_stats(attempts)["mean"],
            "requests_saved": int(_calc_stats(saved)["mean"]),
            "runs": runs[:3],  # Lưu mẫu 3 run đầu tiên
        }

    # 3. Tính calibration error so với delivered SLI thực tế của Reflex
    calibration_error = round(abs(world.actual_delivered_quality - reflex_mean_quality), 4)

    doc: dict[str, Any] = {
        "_id": replay_id,
        "incident_id": incident_key,
        "status": "completed",
        "calibration_error": calibration_error,
        "seeds": k,
        "variants": variant_results,
        "created_at": now,
        "completed_at": now,
    }

    if db is not None:
        await db[REPLAYS].update_one({"_id": replay_id}, {"$set": doc}, upsert=True)
        logger.info(
            "Completed Time Machine replay %s for incident %s (calibration_error=%.4f)",
            replay_id,
            incident_key,
            calibration_error,
        )

    return doc
