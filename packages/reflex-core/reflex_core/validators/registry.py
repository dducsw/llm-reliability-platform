"""Map chuỗi khai báo trong policy → instance validator."""

from __future__ import annotations

from reflex_core.validators.base import CheckResult, NormalizedResponse, Validator


def build_chain(specs: list[str]) -> list[Validator]:
    """vd ["not_empty", "json_schema:order_v2", "no_truncation"]."""
    raise NotImplementedError


def run_chain(chain: list[Validator], response: NormalizedResponse) -> list[CheckResult]:
    raise NotImplementedError
