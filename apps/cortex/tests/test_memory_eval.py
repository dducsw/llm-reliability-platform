from __future__ import annotations

import pytest
from reflex_cortex import context_pack, memory
from reflex_cortex.eval import harness, metrics


@pytest.mark.asyncio
async def test_cortex_memory_remember_synthetic_fallback() -> None:
    # Test remember với db=None
    res = await memory.remember("INC-MEM-TEST", db=None)
    assert res is None

    # Test hàm sinh vector synthetic 64D
    vec_quality = memory._generate_synthetic_vector("quality")
    assert len(vec_quality) == 64
    assert any(v > 0 for v in vec_quality[16:32])  # c2 elevated

    vec_latency = memory._generate_synthetic_vector("latency")
    assert len(vec_latency) == 64
    assert any(v > 0 for v in vec_latency[32:48])  # c3 elevated


@pytest.mark.asyncio
async def test_context_pack_build_offline() -> None:
    pack = await context_pack.build("INC-PACK-TEST", db=None)
    assert pack["incident_key"] == "INC-PACK-TEST"
    assert "incident" in pack
    assert "policy" in pack
    assert "side_diagnosis" in pack
    assert "top_contributors" in pack


def test_eval_metrics_score() -> None:
    pred = {"side": "provider", "cause_class": "output_truncation", "action_type": "shift_weight"}
    gt = {"side": "provider", "cause_class": "output_truncation", "action_type": "shift_weight"}
    scores = metrics.score(pred, gt)
    assert scores["side_acc"] == 1.0
    assert scores["cause_acc"] == 1.0
    assert scores["action_acc"] == 1.0
    assert scores["overall_score"] == 1.0


@pytest.mark.asyncio
async def test_eval_harness_run() -> None:
    summary = await harness.run(scenarios=["silent-brownout"])
    assert summary["scenarios_evaluated"] >= 1
    assert summary["mean_side_acc"] == 1.0
    assert summary["mean_cause_acc"] == 1.0
