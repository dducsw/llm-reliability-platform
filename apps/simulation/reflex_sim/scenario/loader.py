from __future__ import annotations

from pathlib import Path

from reflex_sim.scenario.model import Scenario


def load(name_or_path: str, directory: Path = Path("scenarios")) -> Scenario:
    raise NotImplementedError
