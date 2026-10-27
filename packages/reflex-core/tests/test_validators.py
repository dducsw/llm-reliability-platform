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
    assert not v.check(
        NormalizedResponse(content="cut", finish_reason="length", route="chat")
    ).passed


def test_validator_chain() -> None:
    chain = build_chain(["not_empty", "no_truncation"])
    results = run_chain(
        chain, NormalizedResponse(content="OK message", finish_reason="stop", route="chat")
    )
    assert len(results) == 2
    assert all(r.passed for r in results)


def test_length_validator() -> None:
    chain = build_chain(["length:5-20"])
    assert len(chain) == 1

    def ok(text: str) -> bool:
        return (
            chain[0]
            .check(NormalizedResponse(content=text, finish_reason="stop", route="chat"))
            .passed
        )

    assert ok("hello world")
    assert not ok("  hi  ")
    assert not ok("x" * 21)
    open_ended = build_chain(["length:3-"])[0]
    assert open_ended.check(
        NormalizedResponse(content="x" * 10_000, finish_reason="stop", route="chat")
    ).passed


def test_mock_outputs_pass_seeded_route_validators() -> None:
    """Output mock (mock-llm, chaos-proxy, adapter mock) phải qua validator của policy seed —
    nếu không, mọi request mock bị coi là quality fail và rescue chạy vô ích."""
    import random
    from pathlib import Path

    import yaml
    from reflex_core.mock_outputs import generate

    seeds = Path(__file__).parents[3] / "seeds" / "policies.yaml"
    for policy in yaml.safe_load(seeds.read_text(encoding="utf-8")):
        route = policy["_id"]
        content = generate(route, [{"role": "user", "content": "xin chào"}], random.Random(1))
        results = run_chain(
            build_chain(policy.get("validators", [])),
            NormalizedResponse(content=content, finish_reason="stop", route=route),
        )
        failed = [(r.name, r.reason) for r in results if not r.passed]
        assert not failed, f"{route}: {failed}"


def test_cortex_output_accepts_tool_turns_and_final_only() -> None:
    import json

    chain = build_chain(["not_empty", "json_schema:cortex_output"])

    def ok(obj: object) -> bool:
        r = NormalizedResponse(content=json.dumps(obj), finish_reason="stop", route="cortex.reason")
        return all(x.passed for x in run_chain(chain, r))

    assert ok({"tool": "dd.logs_search", "args": {"query": "service:gateway"}})
    assert ok({"final": {"hypotheses": [], "recommendation": None}})
    assert not ok({"final": {"hypotheses": []}})  # thiếu recommendation
    assert not ok({"answer": "free text"})
