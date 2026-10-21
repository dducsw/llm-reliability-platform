"""Export JSON Schema từ Pydantic (reflex-core) → infra/mongo/validators/*.json."""

from __future__ import annotations

import json
from pathlib import Path

from reflex_core.actions import Action
from reflex_core.incident import Incident
from reflex_core.policy import Policy

OUT_DIR = Path("infra/mongo/validators")

MODELS = {
    "policies": Policy,
    "incidents": Incident,
    "actions": Action,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        # MongoDB collMod format: {"$jsonSchema": schema}
        validator_payload = {"$jsonSchema": schema}
        out_file = OUT_DIR / f"{name}.json"
        out_file.write_text(json.dumps(validator_payload, indent=2), encoding="utf-8")
        print(f"Exported validator: {out_file}")


if __name__ == "__main__":
    main()
