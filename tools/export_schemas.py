"""Export JSON Schema từ Pydantic (reflex-core) → infra/mongo/validators/*.json.

MongoDB $jsonSchema không hỗ trợ $defs/$ref (gây lỗi Unknown $jsonSchema keyword: $defs).
Script này inline đệ quy toàn bộ $defs/$ref thành JSON Schema phẳng hợp lệ cho collMod.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from reflex_core.actions import Action
from reflex_core.incident import Incident
from reflex_core.policy import Policy

OUT_DIR = Path("infra/mongo/validators")

MODELS = {
    "policies": Policy,
    "incidents": Incident,
    "actions": Action,
}


def inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Thay thế đệ quy toàn bộ $ref trỏ tới $defs và loại bỏ $defs gốc."""
    defs = schema.pop("$defs", {})

    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                if ref.startswith("#/$defs/"):
                    def_name = ref.split("/")[-1]
                    if def_name in defs:
                        resolved = copy.deepcopy(defs[def_name])
                        extra = {k: v for k, v in node.items() if k != "$ref"}
                        resolved_node = _resolve(resolved)
                        if isinstance(resolved_node, dict):
                            resolved_node.update({k: _resolve(v) for k, v in extra.items()})
                        return resolved_node
            return {k: _resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        return node

    return _resolve(schema)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        raw_schema = model.model_json_schema()
        schema = inline_schema(raw_schema)
        # MongoDB collMod format: {"$jsonSchema": schema}
        validator_payload = {"$jsonSchema": schema}
        out_file = OUT_DIR / f"{name}.json"
        out_file.write_text(json.dumps(validator_payload, indent=2), encoding="utf-8")
        print(f"Exported validator: {out_file}")


if __name__ == "__main__":
    main()

