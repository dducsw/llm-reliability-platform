import json

import pytest
from reflex_cortex.agent import CortexAgent, parse_json_object
from reflex_cortex.settings import Settings


class ScriptedLlm:
    def __init__(self, replies: list[str]) -> None:
        self.replies, self.seen = list(replies), []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.seen.append(messages)
        return self.replies.pop(0)


def _final(evidence_ref: str, rec: dict | None = None) -> str:
    return json.dumps(
        {
            "final": {
                "side": "provider",
                "hypotheses": [
                    {
                        "id": "H1",
                        "statement": "truncation",
                        "confidence": 0.9,
                        "evidence": [{"type": "log", "ref": evidence_ref, "claim": "x"}],
                    }
                ],
                "recommendation": rec
                or {
                    "action_type": "shift_weight",
                    "params": {
                        "route": "order.extract",
                        "from": "vendorA:large",
                        "to": "vendorB:large",
                        "pct": 1.0,
                    },
                },
            }
        }
    )


def test_parse_json_object_tolerates_fences_and_prose() -> None:
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('ok: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        parse_json_object("no json here")


@pytest.mark.asyncio
async def test_loop_calls_tool_then_accepts_valid_evidence() -> None:
    llm = ScriptedLlm(
        [
            json.dumps({"tool": "dd.logs_search", "args": {"query": "service:x"}}),
            _final("dd_logs_search_1"),
        ]
    )
    inv = await CortexAgent(db=None, llm=llm, settings=Settings()).investigate("INC-1")
    assert [s.tool for s in inv.steps] == ["dd.logs_search"]
    assert inv.hypotheses[0].confidence == 0.9  # ref tồn tại → giữ nguyên
    assert inv.recommendation and inv.recommendation.action_type == "shift_weight"
    assert "Datadog API not configured" in llm.seen[-1][-1]["content"]


@pytest.mark.asyncio
async def test_invented_evidence_ref_lowers_confidence() -> None:
    inv = await CortexAgent(
        db=None, llm=ScriptedLlm([_final("made_up_9")]), settings=Settings()
    ).investigate("INC-1")
    assert inv.hypotheses[0].confidence <= 0.45


@pytest.mark.asyncio
async def test_off_catalog_recommendation_falls_back_to_rules() -> None:
    bad = {"action_type": "drop_database", "params": {}}
    inv = await CortexAgent(
        db=None, llm=ScriptedLlm([_final("x", bad)]), settings=Settings()
    ).investigate("INC-1")
    assert (
        inv.recommendation and inv.recommendation.action_type == "shift_weight"
    )  # từ rules (sli=quality)


@pytest.mark.asyncio
async def test_unknown_tool_is_reported_not_crashed() -> None:
    llm = ScriptedLlm([json.dumps({"tool": "rm.rf", "args": {}}), _final("x")])
    inv = await CortexAgent(db=None, llm=llm, settings=Settings()).investigate("INC-1")
    assert inv.steps[0].result_ref is None and "unknown tool" in (inv.steps[0].result_digest or "")


@pytest.mark.asyncio
async def test_tool_budget_exhaustion_falls_back_to_rules() -> None:
    call = json.dumps({"tool": "dd.logs_search", "args": {"query": "q"}})
    llm = ScriptedLlm([call] * 5)
    inv = await CortexAgent(db=None, llm=llm, settings=Settings(max_tool_calls=2)).investigate(
        "INC-1"
    )
    assert len(inv.steps) == 2
    assert inv.hypotheses[0].id == "H-rules" and inv.hypotheses[0].confidence <= 0.4


@pytest.mark.asyncio
async def test_llm_failure_still_produces_rule_based_recommendation() -> None:
    class Down:
        async def chat(self, messages: list[dict[str, str]]) -> str:
            raise ConnectionError("gateway down")

    inv = await CortexAgent(db=None, llm=Down(), settings=Settings()).investigate("INC-1")
    assert inv.recommendation is not None and inv.hypotheses[0].id == "H-rules"


def test_action_params_doc_matches_catalog_aliases() -> None:
    from reflex_cortex.agent import action_params_doc

    doc = action_params_doc()
    assert (
        "- shift_weight: {route: string, from: string, to: string, pct: number (0.0..1.0]}" in doc
    )
    assert "page_human" in doc
