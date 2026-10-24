import pytest
from reflex_cp.timemachine.des import simulate
from reflex_cp.timemachine.jobs import run_replay
from reflex_cp.timemachine.world import World


@pytest.mark.asyncio
async def test_world_load() -> None:
    world = await World.load("INC-TEST-001", db=None)
    assert len(world.demand) == 1200
    assert world.incident_key == "INC-TEST-001"

    # Lấy mẫu ngẫu nhiên từ target
    import random

    rng = random.Random(42)
    outcome, lat, ttft = world.sample_target("vendorA:large", world.demand[0].ts, rng)
    assert outcome in ("ok", "quality_fail")
    assert lat > 0
    assert ttft > 0


def test_des_simulate_variants() -> None:
    from datetime import UTC, datetime

    from reflex_cp.timemachine.world import DemandRequest

    # Dựng world mini gồm 100 requests
    now = datetime.now(tz=UTC)
    demand = [DemandRequest(request_id=f"r_{i}", ts=now, route="order.extract") for i in range(100)]
    world = World("INC-TEST-002", demand=demand)

    # 1. Naive: Không retry, quality tụt ~65% do vendorA lỗi
    res_naive = simulate(world, "naive", seed=42)
    assert res_naive["attempts_per_request"] == 1.0
    assert res_naive["delivered_quality"] < 0.85

    # 2. Static failover: Không bắt được quality lỗi nên kết quả vẫn thấp
    res_static = simulate(world, "static_failover", seed=42)
    assert res_static["delivered_quality"] < 0.85

    # 3. Reflex: Bắt lỗi quality và cứu qua vendorB -> chất lượng >= 98%
    res_reflex = simulate(world, "reflex_recorded", seed=42)
    assert res_reflex["delivered_quality"] >= 0.98
    assert res_reflex["requests_saved"] > 0
    assert res_reflex["attempts_per_request"] > 1.0


@pytest.mark.asyncio
async def test_jobs_run_replay() -> None:
    result = await run_replay(
        "INC-TEST-003", variants=["naive", "reflex_recorded"], k=5, seed=42, db=None
    )
    assert result["status"] == "completed"
    assert "naive" in result["variants"]
    assert "reflex_recorded" in result["variants"]
    assert result["calibration_error"] >= 0.0
    assert result["variants"]["reflex_recorded"]["delivered_quality"] >= 0.95
