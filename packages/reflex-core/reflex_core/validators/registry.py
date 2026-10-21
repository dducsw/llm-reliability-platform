"""Map chuỗi khai báo trong policy → instance validator."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse, Validator
from reflex_core.validators.json_schema import JsonSchemaValidator
from reflex_core.validators.lang import LangValidator
from reflex_core.validators.not_empty import NotEmptyValidator
from reflex_core.validators.refusal import RefusalValidator
from reflex_core.validators.truncation import TruncationValidator


def build_chain(specs: list[str]) -> list[Validator]:
    """vd ["not_empty", "json_schema:order_v2", "no_truncation"]."""
    chain: list[Validator] = []
    for spec in specs:
        s = spec.strip()
        if s == "not_empty":
            chain.append(NotEmptyValidator())
        elif s.startswith("json_schema:"):
            schema_name = s.split(":", 1)[1]
            chain.append(JsonSchemaValidator(schema_name))
        elif s in ("no_truncation", "truncation"):
            chain.append(TruncationValidator())
        elif s == "refusal":
            chain.append(RefusalValidator())
        elif s == "lang":
            chain.append(LangValidator())
    return chain


def run_chain(chain: list[Validator], response: NormalizedResponse) -> list[CheckResult]:
    return [v.check(response) for v in chain]
