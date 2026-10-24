"""JSON Schema export của models khớp infra/mongo/validators."""

import json
from pathlib import Path


def test_validator_schemas_match_models() -> None:
    validator_dir = Path("infra/mongo/validators")
    assert (validator_dir / "policies.json").exists()
    assert (validator_dir / "incidents.json").exists()
    assert (validator_dir / "actions.json").exists()

    pol_data = json.loads((validator_dir / "policies.json").read_text(encoding="utf-8"))
    assert pol_data["$jsonSchema"]["title"] == "Policy"

    inc_data = json.loads((validator_dir / "incidents.json").read_text(encoding="utf-8"))
    assert inc_data["$jsonSchema"]["title"] == "Incident"

    act_data = json.loads((validator_dir / "actions.json").read_text(encoding="utf-8"))
    assert act_data["$jsonSchema"]["title"] == "Action"
