"""Registry pipeline ID → module, phục vụ Query Explorer (/api/pipelines/:id)."""

from __future__ import annotations

from types import ModuleType

from reflex_mongo.pipelines import (
    a01_attempt_rollup,
    a02_request_rollup,
    a03_hourly_rollup,
    a04_burn_rate,
    a05_budget_remaining,
    a06_anomaly,
    a07_probe_blindness,
    a08_first_bad_at,
    a09_signature,
    a10_similar_incidents,
    a11_side_diagnosis,
    a12_top_contributors,
    a13_blast_radius,
    a14_baselines,
    a15_bench_incidents,
    a16_recovery_proof,
    a17_mttx,
    a18_cost_daily,
)

REGISTRY: dict[str, ModuleType] = {
    a01_attempt_rollup.ID: a01_attempt_rollup,
    a02_request_rollup.ID: a02_request_rollup,
    a03_hourly_rollup.ID: a03_hourly_rollup,
    a04_burn_rate.ID: a04_burn_rate,
    a05_budget_remaining.ID: a05_budget_remaining,
    a06_anomaly.ID: a06_anomaly,
    a07_probe_blindness.ID: a07_probe_blindness,
    a08_first_bad_at.ID: a08_first_bad_at,
    a09_signature.ID: a09_signature,
    a10_similar_incidents.ID: a10_similar_incidents,
    a11_side_diagnosis.ID: a11_side_diagnosis,
    a12_top_contributors.ID: a12_top_contributors,
    a13_blast_radius.ID: a13_blast_radius,
    a14_baselines.ID: a14_baselines,
    a15_bench_incidents.ID: a15_bench_incidents,
    a16_recovery_proof.ID: a16_recovery_proof,
    a17_mttx.ID: a17_mttx,
    a18_cost_daily.ID: a18_cost_daily,
}


def get(pipeline_id: str) -> ModuleType:
    return REGISTRY[pipeline_id]
