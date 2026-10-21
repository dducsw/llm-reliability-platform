"""Parse JSON + validate bằng fastjsonschema (schema theo tên, vd order_v2)."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse


class JsonSchemaValidator:
    name = "json_schema"

    def check(self, response: NormalizedResponse) -> CheckResult:
        raise NotImplementedError
