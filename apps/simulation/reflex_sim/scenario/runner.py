"""Ghi từng phase vào chaos_runs, gửi Datadog event scenario.phase, --fast = time scale ×60."""

from __future__ import annotations

from reflex_sim.scenario.model import Scenario


class ScenarioRunner:
    async def run(self, scenario: Scenario, seed: int, fast: bool = False) -> dict:
        raise NotImplementedError
