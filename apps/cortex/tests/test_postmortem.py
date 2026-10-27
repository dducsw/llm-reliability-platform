import json
from datetime import UTC, datetime, timedelta

import pytest
from reflex_cortex.postmortem import write_postmortem

T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)


def _facts() -> dict:
    return {
        "incident": {
            "key": "INC-20261021-0010",
            "target": "vendorA:large",
            "routes": ["order.extract"],
            "sli": "quality",
            "severity": "critical",
            "t": {
                "first_bad_at": T0,
                "detected_at": T0 + timedelta(minutes=2),
                "mitigated_at": T0 + timedelta(minutes=5),
                "resolved_at": T0 + timedelta(minutes=20),
            },
            "impact": {"requests": 1500, "delivered_bad": 30, "extra_cost_usd": 2.4},
            "diagnosis": {
                "side": "provider",
                "hypothesis": "Provider output truncation",
                "confidence": 0.86,
                "by": "cortex",
            },
            "timeline": [
                {"at": T0 + timedelta(minutes=2), "kind": "detected", "actor": "sentinel"}
            ],
        },
        "actions": [
            {
                "type": "shift_weight",
                "state": "verified",
                "params": {"route": "order.extract", "pct": 1.0},
                "verification": {"verdict": "PASS"},
            }
        ],
        "investigation": {
            "hypotheses": [
                {
                    "id": "H1",
                    "statement": "finish_reason=length spike",
                    "confidence": 0.86,
                    "evidence": [{"type": "metric", "ref": "contrib_1", "claim": "92% length"}],
                }
            ]
        },
    }


class FakeLlm:
    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.prompts.append(messages[-1]["content"])
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.mark.asyncio
async def test_postmortem_facts_only() -> None:
    pm = await write_postmortem("INC-20261021-0010", facts=_facts())
    assert pm["_id"] == "pm-INC-20261021-0010"
    assert pm["generated_by"] == "cortex"
    assert "vendorA:large" in pm["title"]
    assert "quality" in pm["tags"]
    body = pm["body_md"]
    assert "MTTD (first bad → detected): 2.0 phút" in body
    assert "MTTR (detected → resolved): 18.0 phút" in body
    assert "verify: **PASS**" in body
    assert "`contrib_1`" in body
    assert "cần bổ sung thủ công" in body


@pytest.mark.asyncio
async def test_postmortem_with_llm_narrative() -> None:
    llm = FakeLlm(
        "```json\n"
        + json.dumps(
            {
                "summary": "Vendor A cắt cụt output; Reflex chuyển traffic sau 3 phút.",
                "went_well": ["Rescue giữ delivered quality"],
                "went_poorly": ["Phát hiện chậm 2 phút"],
                "action_items": ["Thêm monitor tỉ lệ finish_reason=length"] * 10,
                "execute": "drop table",
            }
        )
        + "\n```"
    )
    pm = await write_postmortem("INC-20261021-0010", facts=_facts(), llm=llm)
    assert pm["generated_by"] == "cortex+llm"
    assert pm["summary"].startswith("Vendor A")
    assert "- Rescue giữ delivered quality" in pm["body_md"]
    assert pm["body_md"].count("Thêm monitor tỉ lệ") == 6
    assert "drop table" not in pm["body_md"]
    # Số liệu chỉ đến từ facts, LLM chỉ nhận bản tóm gọn
    assert '"delivered_bad": 30' in llm.prompts[0]


@pytest.mark.asyncio
async def test_postmortem_llm_failure_falls_back() -> None:
    pm = await write_postmortem(
        "INC-20261021-0010", facts=_facts(), llm=FakeLlm(TimeoutError("gateway"))
    )
    assert pm["generated_by"] == "cortex"
    assert "Provider output truncation" in pm["summary"]


@pytest.mark.asyncio
async def test_postmortem_requires_source() -> None:
    with pytest.raises(ValueError):
        await write_postmortem("INC-x")
