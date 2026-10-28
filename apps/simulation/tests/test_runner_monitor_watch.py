"""Monitor Datadog chỉ Alert lúc fault đang chạy → runner phải theo dõi song song, không đợi hết scenario."""

import asyncio
import time
from typing import Any

import pytest
from reflex_sim.scenario import expectations
from reflex_sim.scenario.model import Scenario
from reflex_sim.scenario.runner import ScenarioRunner


class _Coll:
    async def insert_one(self, _doc: dict[str, Any]) -> None:
        pass

    async def update_many(self, *_a: Any, **_k: Any) -> None:
        pass


class _Dd:
    """Alert trong 0.6s đầu kể từ lúc tạo rồi về OK (như M3 khi fault hết)."""

    def __init__(self) -> None:
        self.t0 = time.monotonic()

    async def find_monitors(self, _name: str) -> list[dict[str, Any]]:
        state = "Alert" if time.monotonic() - self.t0 < 0.6 else "OK"
        return [{"name": "M3_quality_fast_burn", "overall_state": state}]


def _scenario() -> Scenario:
    return Scenario.model_validate(
        {
            "name": "t",
            "traffic": {"rps": 1, "mix": {"r": 1.0}},
            "phases": [{"at": "0s", "duration": "1s"}, {"at": "1s", "duration": "1s"}],
            "expectations": [
                {"monitor": "M3_quality_fast_burn", "state": "Alert", "within": "5s"},
                {
                    "delivered_sli": {"route": "r", "sli": "quality", "min": 0.9},
                    "window": ["0s", "1s"],
                },
            ],
        }
    )


@pytest.mark.asyncio
async def test_monitor_is_watched_during_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(expectations, "MONITOR_POLL_S", 0.05)
    dd = _Dd()
    runner = ScenarioRunner(db={"chaos_runs": _Coll()}, dd=dd)  # type: ignore[arg-type]

    async def sli(*_a: Any, **_k: Any) -> dict[str, Any]:
        return expectations._result({}, None, "stub")

    monkeypatch.setattr(expectations, "_check_delivered_sli", sli)
    res = await asyncio.wait_for(runner.run(_scenario(), scale=1.0), timeout=20)
    monitor, sli_res = res["expectations"]
    assert monitor["passed"] is True, monitor
    assert sli_res["detail"] == "stub"  # thứ tự expectations được giữ nguyên
