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
from reflex_core.actions import CATALOG, ActionType, validate_params
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
from reflex_core.rules import RULES_ACTOR_LLM_REJECTED, RULES_CONFIDENCE, classify
from reflex_mongo.collections import INCIDENTS, INVESTIGATIONS
from reflex_mongo.serde import to_doc
from reflex_telemetry import llmobs
from reflex_telemetry import tags as t
from reflex_telemetry.datadog_api import DatadogApi
from reflex_telemetry.setup import make_statsd

from reflex_cortex.context_pack import build as build_context_pack
from reflex_cortex.evidence import validate
from reflex_cortex.settings import Settings
from reflex_cortex.tools import build_toolbox, signature
from reflex_cortex.tools.propose import propose_action

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
        with llmobs.span(
            "llm", "cortex.llm", model_name=self._route, model_provider="reflex-gateway"
        ) as s:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(
                    self._url,
                    json={"model": self._route, "messages": messages},
                    headers={"x-reflex-route": self._route, "x-priority": "0"},
                )
            resp.raise_for_status()
            body = resp.json()
            content: str = body["choices"][0]["message"]["content"]
            usage = body.get("usage") or {}
            llmobs.annotate(
                s,
                input_data=messages,
                output_data=[{"role": "assistant", "content": content}],
                metrics={
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                tags={"reflex.target": resp.headers.get("x-reflex-target", "")},
            )
            return content


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


def _bounds(prop: dict[str, Any]) -> str:
    lo = prop.get("minimum", prop.get("exclusiveMinimum"))
    hi = prop.get("maximum", prop.get("exclusiveMaximum"))
    if lo is None and hi is None:
        return ""
    left = "(" if "exclusiveMinimum" in prop else "["
    right = ")" if "exclusiveMaximum" in prop else "]"
    return f" {left}{'' if lo is None else lo}..{'' if hi is None else hi}{right}"


def _type_name(prop: dict[str, Any]) -> str:
    """JSON Schema type; Optional[X] (anyOf [X, null]) → X."""
    if "type" in prop:
        return str(prop["type"])
    kinds = [str(o["type"]) for o in prop.get("anyOf", []) if o.get("type") not in (None, "null")]
    return kinds[0] if kinds else "any"


def action_params_doc() -> str:
    """Tham số từng action (sinh từ CATALOG, khớp đúng validator) — LLM thật không đoán được."""
    lines = []
    for action_type, spec in CATALOG.items():
        schema = spec.params_model.model_json_schema(by_alias=True)
        required = set(schema.get("required", []))
        fields = ", ".join(
            f"{name}{'' if name in required else '?'}: {_type_name(prop)}{_bounds(prop)}"
            for name, prop in schema.get("properties", {}).items()
        )
        lines.append(f"- {action_type.value}: {{{fields}}}")
    return "\n".join(lines)


def untrusted(text: str) -> str:
    """Bọc kết quả tool (log/span/postmortem…) để LLM coi là dữ liệu, không phải chỉ dẫn."""
    return f"<untrusted_data>\n{text.replace('</untrusted_data>', '')}\n</untrusted_data>"


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
        statsd: Any = None,
    ) -> None:
        self.statsd = statsd
        self.db = db
        self.model = model
        self.settings = settings or Settings()
        self.llm = llm or GatewayLlm(self.settings.gateway_url, self.settings.reason_route)
        self.datadog = datadog
        self._statsd = make_statsd("reflex-cortex", self.settings.reflex_env, "0.1.0")

    async def investigate(self, incident_key: str, lease: str | None = None) -> Investigation:
        """Dựng context pack → vòng lặp LLM+tool (có giới hạn) → validate evidence → lưu.

        `lease` (từ `claim`): chỉ ghi diagnosis/propose khi incident vẫn do lần claim này giữ —
        watchdog control-plane có thể đã tiếp quản nếu Cortex chậm quá ngưỡng.
        """
        started = time.monotonic()
        try:
            inv = await self._traced_investigate(incident_key, lease)
        except Exception:
            self._emit_failure(time.monotonic() - started)
            raise
        return inv

    def _emit_failure(self, seconds: float) -> None:
        """Metric cho M13 khi điều tra ném exception (đường thành công phát ở cuối `_investigate`)."""
        if self.statsd is None:
            return
        tags = [f"status:{InvestigationStatus.FAILED.value}"]
        self.statsd.distribution(t.M_CORTEX_DURATION, seconds, tags=tags)
        self.statsd.increment(t.M_CORTEX_INVESTIGATION, tags=tags)

    async def _traced_investigate(self, incident_key: str, lease: str | None) -> Investigation:
        with llmobs.span("agent", "cortex.investigate", session_id=incident_key) as s:
            inv = await self._investigate(incident_key, lease)
            rec = inv.recommendation
            llmobs.annotate(
                s,
                input_data={"incident_id": incident_key},
                output_data={
                    "action_type": rec.action_type if rec else None,
                    "params": rec.params if rec else None,
                    "hypotheses": [h.statement for h in inv.hypotheses],
                },
                metrics={"tool_calls": len(inv.steps)},
                tags={"incident_id": incident_key, "investigation_id": inv.id or ""},
            )
            return inv

    async def _investigate(self, incident_key: str, lease: str | None = None) -> Investigation:
        start_time = time.monotonic()
        with llmobs.span("task", "cortex.context_pack") as s:
            context_pack = await build_context_pack(incident_key, self.db)
            llmobs.annotate(s, input_data={"incident_id": incident_key}, output_data=context_pack)
        rule_rec = classify(context_pack)
        llm_rejected = False  # LLM có trả lời nhưng đề xuất bị loại → có thể bị dắt (injection)

        steps: list[ToolStep] = []
        results: dict[str, Any] = {}
        try:
            with llmobs.span("workflow", "cortex.reason") as ws:
                final = await self._reason(incident_key, context_pack, steps, results)
                llmobs.annotate(ws, output_data=final, metrics={"tool_calls": len(steps)})
            hypotheses = [Hypothesis.model_validate(h) for h in final.get("hypotheses", [])]
            rec = _safe_recommendation(final.get("recommendation"), rule_rec)
            llm_rejected = bool(final.get("recommendation")) and rec is rule_rec
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
        from_rules = rec is not None and rec is rule_rec
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
        owned = await self._persist(investigation, validated, side, lease)
        if not owned:
            logger.warning(
                "Cortex lost incident %s to the watchdog; dropping its proposal", incident_key
            )
        elif rec is not None:
            best = max((h.confidence for h in validated), default=0.0)
            await self._propose(
                investigation,
                rec,
                actor=(RULES_ACTOR_LLM_REJECTED if llm_rejected else "rules")
                if from_rules
                else "cortex",
                confidence=RULES_CONFIDENCE if from_rules else best,
            )
        duration_s = time.monotonic() - start_time
        invalid_count = sum(
            1
            for h in validated
            if h.confidence < 0.50
            and any(
                ev.ref not in set(results.keys()) | {s.result_ref for s in steps if s.result_ref}
                for ev in h.evidence
            )
        )
        try:
            self._statsd.increment(
                "reflex.cortex.investigation",
                tags=[f"status:{investigation.status.value}"],
            )
            self._statsd.distribution(
                t.M_CORTEX_DURATION,
                duration_s,
                tags=[f"status:{investigation.status.value}"],
            )
            for s in steps:
                self._statsd.increment(t.M_CORTEX_TOOL_CALLS, tags=[f"tool:{s.tool}"])
            if invalid_count > 0:
                self._statsd.increment(t.M_CORTEX_EVIDENCE_INVALID, value=invalid_count)
        except Exception:
            logger.debug("Failed emitting cortex metrics to statsd", exc_info=True)

        logger.info(
            "Cortex completed investigation %s for incident %s (action=%s, steps=%d, duration=%.2fs)",
            investigation.id,
            incident_key,
            rec.action_type if rec else "none",
            len(steps),
            duration_s,
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
                tools="\n".join(f"- {signature(name, fn)}" for name, fn in toolbox.items()),
            )
        )
        messages = [
            {
                "role": "system",
                "content": (PROMPTS / "system.md").read_text(encoding="utf-8")
                + "\n\n`recommendation.params` theo action (`?` = tùy chọn):\n"
                + action_params_doc(),
            },
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
            with llmobs.span("tool", name or "unknown") as ts:
                if name not in toolbox:
                    digest, data = f"unknown tool `{name}`", None
                else:
                    try:
                        res = await toolbox[name](**args)
                        digest, data = res.digest, res.data
                    except Exception as e:  # tool lỗi là thông tin cho LLM, không phải lỗi vòng lặp
                        digest, data = f"tool error: {e}", None
                llmobs.annotate(ts, input_data=args, output_data=digest, tags={"ref": ref})
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
                {"role": "user", "content": f"Kết quả tool (ref={ref}):\n{untrusted(digest)}"},
            ]

    async def _propose(
        self, inv: Investigation, rec: Recommendation, actor: str, confidence: float
    ) -> None:
        """Ghi action `proposed`; policy engine ở control-plane quyết định auto hay chờ duyệt."""
        if self.db is None:
            return
        try:
            await propose_action(
                incident_key=inv.incident_id,
                action_type=rec.action_type,
                params=rec.params,
                confidence=confidence,
                db=self.db,
                actor=actor,
                investigation_id=inv.id,
            )
        except Exception:
            logger.exception("propose_action failed for %s", inv.incident_id)

    async def _persist(
        self, inv: Investigation, hypotheses: list[Hypothesis], side: Side, lease: str | None
    ) -> bool:
        """Lưu investigation (luôn, để audit) + diagnosis; False nếu đã mất quyền với incident."""
        if self.db is None:
            return True
        await self.db[INVESTIGATIONS].insert_one(to_doc(inv))
        best = max(hypotheses, key=lambda h: h.confidence, default=None)
        diag = Diagnosis(
            side=side,
            hypothesis=best.statement if best else "Unknown",
            confidence=best.confidence if best else 0.0,
            by="cortex",
            investigation_id=inv.id,
        )
        flt: dict[str, Any] = {"$or": [{"key": inv.incident_id}, {"_id": inv.incident_id}]}
        if lease is not None:
            flt |= {"investigator": "cortex", "investigating_since": lease}
        res = await self.db[INCIDENTS].update_one(
            flt,
            {
                "$set": {
                    "diagnosis": diag.model_dump(mode="json"),
                    "status": IncidentStatus.MITIGATING.value,
                }
            },
        )
        return lease is None or res.modified_count == 1
