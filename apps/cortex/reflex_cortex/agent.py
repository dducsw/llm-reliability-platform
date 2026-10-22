"""Reasoning loop: LLM (qua gateway) + read-only tools, ≤ 12 tool calls, ≤ 90s, structured output.
LLMObs: agent → workflow → tool → llm span, tag incident_id.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Protocol

import httpx
from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import ActionType, validate_params
from reflex_core.incident import (
    Diagnosis,
    Hypothesis,
    IncidentStatus,
    Investigation,
    InvestigationStatus,
    Recommendation,
    Side,
    ToolStep,
)
from reflex_mongo.collections import INCIDENTS, INVESTIGATIONS
from reflex_telemetry.datadog_api import DatadogApi

from reflex_cortex.context_pack import build as build_context_pack
from reflex_cortex.evidence import validate
from reflex_cortex.rules import classify
from reflex_cortex.settings import Settings
from reflex_cortex.tools import build_toolbox

logger = logging.getLogger(__name__)

PROMPTS = Path(__file__).parent / "prompts"


class LlmClient(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


class GatewayLlm:
    """Gọi LLM qua chính Reflex gateway (route `cortex.reason`) — Cortex được bảo vệ bởi Reflex."""

    def __init__(self, base_url: str, route: str, timeout_s: float = 30.0) -> None:
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self._route = route
        self._timeout_s = timeout_s

    async def chat(self, messages: list[dict[str, str]]) -> str:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            resp = await client.post(
                self._url,
                json={"model": self._route, "messages": messages},
                headers={"x-reflex-route": self._route, "x-priority": "0"},
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def parse_json_object(text: str) -> dict[str, Any]:
    """Lấy JSON object đầu tiên trong output của LLM (chịu được ```json fence và văn bản thừa)."""
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start = stripped.find("{")
    if start < 0:
        raise ValueError("no JSON object in LLM output")
    obj, _ = json.JSONDecoder().raw_decode(stripped[start:])
    if not isinstance(obj, dict):
        raise ValueError("LLM output is not a JSON object")
    return obj


def _safe_recommendation(
    raw: dict[str, Any] | None, fallback: Recommendation | None
) -> Recommendation | None:
    """Đề xuất của LLM phải thuộc catalog và qua validate params; sai → dùng rule engine."""
    if not raw:
        return fallback
    try:
        rec = Recommendation.model_validate(raw)
        validate_params(ActionType(rec.action_type), rec.params)
        return rec
    except Exception as e:
        logger.warning("LLM recommendation rejected (%s); using rule-based one", e)
        return fallback


class CortexAgent:
    def __init__(
        self,
        db: AsyncDatabase | None = None,
        model: str = "cortex-agent-v1",
        llm: LlmClient | None = None,
        settings: Settings | None = None,
        datadog: DatadogApi | None = None,
    ) -> None:
        self.db = db
        self.model = model
        self.settings = settings or Settings()
        self.llm = llm or GatewayLlm(self.settings.gateway_url, self.settings.reason_route)
        self.datadog = datadog

    async def investigate(self, incident_key: str) -> Investigation:
        """Dựng context pack → vòng lặp LLM+tool (có giới hạn) → validate evidence → lưu."""
        context_pack = await build_context_pack(incident_key, self.db)
        rule_rec = classify(context_pack)

        steps: list[ToolStep] = []
        results: dict[str, Any] = {}
        try:
            final = await self._reason(incident_key, context_pack, steps, results)
            hypotheses = [Hypothesis.model_validate(h) for h in final.get("hypotheses", [])]
            rec = _safe_recommendation(final.get("recommendation"), rule_rec)
            side = (
                Side(final.get("side", "unknown"))
                if final.get("side") in {s.value for s in Side}
                else Side.UNKNOWN
            )
        except Exception as e:
            # LLM lỗi/timeout/output sai → rule engine, vẫn đi hết vòng (không cần LLM).
            logger.warning(
                "Cortex LLM path failed for %s (%s); falling back to rules", incident_key, e
            )
            rec, side = rule_rec, Side.UNKNOWN
            hypotheses = [
                Hypothesis(
                    id="H-rules",
                    statement=f"Rule-based classification: {rec.action_type if rec else 'none'}",
                    confidence=0.4,
                    evidence=[],
                )
            ]

        validated = validate(hypotheses, steps, results)
        investigation = Investigation(
            _id=f"inv-{uuid.uuid4().hex[:8]}",
            incident_id=incident_key,
            run_no=1,
            status=InvestigationStatus.COMPLETED,
            model=self.model,
            via_gateway_route=self.settings.reason_route,
            context_pack_ref={"incident_key": incident_key},
            steps=steps,
            hypotheses=validated,
            recommendation=rec,
        )
        await self._persist(investigation, validated, side)
        logger.info(
            "Cortex completed investigation %s for incident %s (action=%s, steps=%d)",
            investigation.id,
            incident_key,
            rec.action_type if rec else "none",
            len(steps),
        )
        return investigation

    async def _reason(
        self,
        incident_key: str,
        context_pack: dict[str, Any],
        steps: list[ToolStep],
        results: dict[str, Any],
    ) -> dict[str, Any]:
        toolbox = build_toolbox(self.db, self.datadog, incident_key)
        user = (
            (PROMPTS / "investigate.md")
            .read_text(encoding="utf-8")
            .format(
                incident_key=incident_key,
                context_pack=json.dumps(context_pack, default=str, ensure_ascii=False)[:8000],
                tools="\n".join(f"- {name}" for name in toolbox),
            )
        )
        messages = [
            {"role": "system", "content": (PROMPTS / "system.md").read_text(encoding="utf-8")},
            {"role": "user", "content": user},
        ]
        deadline = time.monotonic() + self.settings.max_wall_s

        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("investigation exceeded max_wall_s")
            reply = await self.llm.chat(messages)
            msg = parse_json_object(reply)
            if "final" in msg:
                return msg["final"]

            if len(steps) >= self.settings.max_tool_calls:
                raise RuntimeError("tool call budget exhausted without a final answer")
            name, args = msg.get("tool", ""), msg.get("args") or {}
            n = len(steps) + 1
            ref = f"{name.replace('.', '_')}_{n}"
            started = time.perf_counter()
            if name not in toolbox:
                digest, data = f"unknown tool `{name}`", None
            else:
                try:
                    res = await toolbox[name](**args)
                    digest, data = res.digest, res.data
                except Exception as e:  # tool lỗi là thông tin cho LLM, không phải lỗi của vòng lặp
                    digest, data = f"tool error: {e}", None
            results[ref] = data
            steps.append(
                ToolStep(
                    n=n,
                    tool=name,
                    args=args,
                    ms=(time.perf_counter() - started) * 1000.0,
                    result_ref=ref if data is not None else None,
                    result_digest=digest,
                )
            )
            messages += [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": f"Kết quả tool (ref={ref}): {digest}"},
            ]

    async def _persist(self, inv: Investigation, hypotheses: list[Hypothesis], side: Side) -> None:
        if self.db is None:
            return
        await self.db[INVESTIGATIONS].insert_one(inv.model_dump(by_alias=True, mode="json"))
        best = max(hypotheses, key=lambda h: h.confidence, default=None)
        diag = Diagnosis(
            side=side,
            hypothesis=best.statement if best else "Unknown",
            confidence=best.confidence if best else 0.0,
            by="cortex",
            investigation_id=inv.id,
        )
        await self.db[INCIDENTS].update_one(
            {"$or": [{"key": inv.incident_id}, {"_id": inv.incident_id}]},
            {
                "$set": {
                    "diagnosis": diag.model_dump(mode="json"),
                    "status": IncidentStatus.MITIGATING.value,
                }
            },
        )
