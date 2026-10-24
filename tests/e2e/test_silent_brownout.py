"""S1 e2e (testing-strategy.md): incident ≤ 60s, delivered quality ≥ 99%, shift_weight PASS,
resolved sau failback, Memory +1."""

import pytest
from reflex_sim.scenario.loader import load
from reflex_sim.scenario.runner import ScenarioRunner


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_silent_brownout_simulation_fast() -> None:
    scenario = load("silent-brownout")
    runner = ScenarioRunner(db=None)

    # Chạy mô phỏng ở chế độ --fast (tỉ lệ 60x)
    result = await runner.run(scenario, seed=42, fast=True)

    assert result["run_id"].startswith("run-")
    assert result["phases_run"] == len(scenario.phases)
    assert result["all_passed"] is True
