"""Parse JSON + validate bằng fastjsonschema (schema theo tên, vd order_v2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import fastjsonschema

from reflex_core.validators.base import CheckResult, NormalizedResponse


class JsonSchemaValidator:
    def __init__(self, schema_name: str = "order_v2") -> None:
        self.schema_name = schema_name
        self.name = f"json_schema:{schema_name}"
        self._validate_fn: Callable[[Any], Any] | None = None

    def _get_validator(self) -> Callable[[Any], Any]:
        if self._validate_fn is None:
            base_dir = Path(__file__).resolve().parent.parent / "schemas"
            path = base_dir / f"{self.schema_name}.json"
            if path.exists():
                schema = json.loads(path.read_text(encoding="utf-8"))
            else:
                schema = {"type": "object"}
            self._validate_fn = fastjsonschema.compile(schema)
        return self._validate_fn

    def check(self, response: NormalizedResponse) -> CheckResult:
        try:
            data = json.loads(response.content)
            validate = self._get_validator()
            validate(data)
            return CheckResult(name=self.name, passed=True)
        except json.JSONDecodeError as exc:
            return CheckResult(name=self.name, passed=False, reason=f"Invalid JSON: {exc}")
        except fastjsonschema.JsonSchemaException as exc:
            return CheckResult(
                name=self.name, passed=False, reason=f"Schema violation: {exc.message}"
            )
        except Exception as exc:
            return CheckResult(name=self.name, passed=False, reason=str(exc))
