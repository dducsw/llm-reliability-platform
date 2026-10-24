from __future__ import annotations

from pathlib import Path

import yaml

from reflex_sim.scenario.model import Scenario


def load(name_or_path: str, directory: Path = Path("scenarios")) -> Scenario:
    p = Path(name_or_path)
    if not p.exists():
        cand = directory / f"{name_or_path}.yaml"
        if cand.exists():
            p = cand
        else:
            cand2 = directory / f"{name_or_path}.yml"
            if cand2.exists():
                p = cand2
            else:
                raise FileNotFoundError(f"Scenario not found: {name_or_path} in {directory}")

    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return Scenario.model_validate(data)
