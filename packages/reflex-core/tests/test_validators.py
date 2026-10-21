"""Unit tests cho reflex_core.validators."""

from reflex_core.validators.base import NormalizedResponse
from reflex_core.validators.not_empty import NotEmptyValidator
from reflex_core.validators.registry import build_chain, run_chain
from reflex_core.validators.truncation import TruncationValidator


def test_not_empty_validator() -> None:
    v = NotEmptyValidator()
    assert v.check(NormalizedResponse(content="hello", finish_reason="stop", route="chat")).passed
    assert not v.check(NormalizedResponse(content="   ", finish_reason="stop", route="chat")).passed


def test_truncation_validator() -> None:
    v = TruncationValidator()
    assert v.check(NormalizedResponse(content="full", finish_reason="stop", route="chat")).passed
    assert not v.check(NormalizedResponse(content="cut", finish_reason="length", route="chat")).passed


def test_validator_chain() -> None:
    chain = build_chain(["not_empty", "no_truncation"])
    results = run_chain(chain, NormalizedResponse(content="OK message", finish_reason="stop", route="chat"))
    assert len(results) == 2
    assert all(r.passed for r in results)
