from pathlib import Path
from reflex_sim.scenario.loader import load


def test_load_scenario_by_name() -> None:
    sc = load("silent-brownout", directory=Path("scenarios"))
    assert sc.name == "silent-brownout"
    assert sc.profile == "demo"
    assert sc.traffic.rps == 8.0
    assert len(sc.phases) == 3
    assert len(sc.expectations) == 4
    assert sc.ground_truth is not None
    assert sc.ground_truth["cause_class"] == "output_truncation"
