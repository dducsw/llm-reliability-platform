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


_MONGO_UNSUPPORTED = {"$ref", "$defs", "default", "format", "prefixItems", "type", "const"}


def _keywords(node: object, out: set[str]) -> set[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties":
                for sub in value.values():
                    _keywords(sub, out)
                continue
            out.add(key)
            _keywords(value, out)
    elif isinstance(node, list):
        for item in node:
            _keywords(item, out)
    return out


def test_validators_use_mongo_dialect_and_are_up_to_date() -> None:
    """collMod từ chối keyword ngoài dialect Mongo; file phải khớp đúng output của exporter."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("export_schemas", "tools/export_schemas.py")
    assert spec and spec.loader
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)

    for name, model in exporter.MODELS.items():
        on_disk = json.loads(Path(f"infra/mongo/validators/{name}.json").read_text("utf-8"))
        assert on_disk == exporter.build(model), f"{name}.json lỗi thời — chạy `task schemas`"
        bad = _keywords(on_disk["$jsonSchema"], set()) & _MONGO_UNSUPPORTED
        assert not bad, f"{name}: keyword không hỗ trợ {bad}"
