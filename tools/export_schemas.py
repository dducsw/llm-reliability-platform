"""Export JSON Schema từ Pydantic (reflex-core) → infra/mongo/validators/*.json.

MongoDB `$jsonSchema` là tập con của draft-4 kèm `bsonType`, nên schema Pydantic phải
chuẩn hoá trước khi `collMod` (nếu không Atlas trả lỗi và migrate ghi "skipped"):

- inline đệ quy `$defs`/`$ref` (Mongo không hỗ trợ tham chiếu);
- bỏ keyword không hỗ trợ: `default`, `format`, `prefixItems`, `examples`, `const`→`enum`;
- `type` → `bsonType` (integer → int/long, boolean → bool); chuỗi `date-time` → BSON `date`
  (driver lưu `datetime` thành Date, không phải string);
- bỏ `additionalProperties: false` — Pydantic `extra="forbid"` đã chặn ở tầng app, còn
  collection có thể mang field vận hành (vd `_lease`, `embedding`) không nằm trong model.
  Validator giữ vai trò lưới an toàn cho `required`/kiểu/enum.
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

_DROP = {"default", "format", "prefixItems", "examples", "$schema", "discriminator"}
_BSON = {
    "string": "string",
    "number": "number",
    "integer": ["int", "long"],
    "boolean": "bool",
    "object": "object",
    "array": "array",
    "null": "null",
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


def _bson_types(node: dict[str, Any]) -> list[str]:
    raw = node["type"]
    out: list[str] = []
    for t in raw if isinstance(raw, list) else [raw]:
        if t == "string" and node.get("format") == "date-time":
            mapped: str | list[str] = "date"
        else:
            mapped = _BSON[t]
        out.extend(mapped if isinstance(mapped, list) else [mapped])
    return out


def to_mongo(node: Any) -> Any:
    """Chuẩn hoá một schema node (đã inline) sang dialect `$jsonSchema` của MongoDB."""
    if isinstance(node, list):
        return [to_mongo(item) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _DROP or key == "type":
            continue
        if key == "const":
            out["enum"] = [value]
        elif key == "additionalProperties":
            if isinstance(value, dict):
                out[key] = to_mongo(value)
        elif key == "properties":
            out[key] = {name: to_mongo(sub) for name, sub in value.items()}
        elif key in {"items", "anyOf", "oneOf", "allOf", "not"}:
            out[key] = to_mongo(value)
        else:
            out[key] = value
    if "type" in node:
        types = _bson_types(node)
        out["bsonType"] = types[0] if len(types) == 1 else types
    if "items" in out and isinstance(out["items"], list):
        out.pop("items")
    return out


def build(model: Any) -> dict[str, Any]:
    return {"$jsonSchema": to_mongo(inline_schema(model.model_json_schema()))}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        out_file = OUT_DIR / f"{name}.json"
        out_file.write_text(json.dumps(build(model), indent=2) + "\n", encoding="utf-8")
        print(f"Exported validator: {out_file}")


if __name__ == "__main__":
    main()
