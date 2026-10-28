"""Soạn postmortem khi incident resolved → collection postmortems (Atlas Search).

Phần sự kiện (impact, timeline, root cause, action + verdict) dựng deterministic từ Mongo;
LLM (qua gateway) chỉ viết phần tường thuật. LLM lỗi → postmortem vẫn đủ, chỉ thiếu tường thuật.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import ACTIONS, INCIDENTS, INVESTIGATIONS, POSTMORTEMS
from reflex_telemetry import llmobs

from reflex_cortex.agent import LlmClient, parse_json_object

logger = logging.getLogger(__name__)

PROMPTS = Path(__file__).parent / "prompts"
_NARRATIVE_KEYS = ("went_well", "went_poorly", "action_items")
_MAX_ITEMS, _MAX_CHARS = 6, 300


async def gather(incident_key: str, db: AsyncDatabase) -> dict[str, Any]:
    """Incident + actions + investigation mới nhất."""
    inc = await db[INCIDENTS].find_one({"$or": [{"key": incident_key}, {"_id": incident_key}]})
    if inc is None:
        raise LookupError(f"incident {incident_key} not found")
    actions = [
        a async for a in db[ACTIONS].find({"incident_id": incident_key}).sort("created_at", 1)
    ]
    inv = await db[INVESTIGATIONS].find_one({"incident_id": incident_key}, sort=[("run_no", -1)])
    return {"incident": inc, "actions": actions, "investigation": inv}


def _fmt_t(v: Any) -> str:
    return v.strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(v, datetime) else str(v)


def _minutes(a: Any, b: Any) -> str:
    if isinstance(a, datetime) and isinstance(b, datetime):
        return f"{(b - a).total_seconds() / 60:.1f} phút"
    return "—"


def _clean_narrative(raw: dict[str, Any]) -> dict[str, Any]:
    """Output LLM là dữ liệu: chỉ giữ chuỗi, cắt độ dài, không nhận key lạ."""
    out: dict[str, Any] = {}
    if isinstance(raw.get("summary"), str):
        out["summary"] = raw["summary"].strip()[: _MAX_CHARS * 2]
    for key in _NARRATIVE_KEYS:
        items = raw.get(key)
        if isinstance(items, list):
            out[key] = [str(i).strip()[:_MAX_CHARS] for i in items if str(i).strip()][:_MAX_ITEMS]
    return out


def facts_digest(facts: dict[str, Any]) -> dict[str, Any]:
    """Phần dữ liệu đưa cho LLM (đã gọn, không kèm raw doc)."""
    inc = facts["incident"]
    inv = facts.get("investigation") or {}
    return {
        "key": inc.get("key"),
        "target": inc.get("target"),
        "routes": inc.get("routes", []),
        "sli": inc.get("sli"),
        "severity": inc.get("severity"),
        "t": {k: _fmt_t(v) for k, v in (inc.get("t") or {}).items() if v},
        "impact": inc.get("impact") or {},
        "diagnosis": inc.get("diagnosis") or {},
        "hypotheses": [
            {"statement": h.get("statement"), "confidence": h.get("confidence")}
            for h in inv.get("hypotheses", [])
        ],
        "actions": [
            {
                "type": a.get("type"),
                "state": a.get("state"),
                "params": a.get("params"),
                "verdict": (a.get("verification") or {}).get("verdict"),
            }
            for a in facts.get("actions", [])
        ],
    }


async def narrate(llm: LlmClient, facts: dict[str, Any]) -> dict[str, Any]:
    user = (
        (PROMPTS / "postmortem.md")
        .read_text(encoding="utf-8")
        .format(facts=json.dumps(facts_digest(facts), default=str, ensure_ascii=False)[:8000])
    )
    reply = await llm.chat([{"role": "user", "content": user}])
    return _clean_narrative(parse_json_object(reply))


def render(facts: dict[str, Any], narrative: dict[str, Any], now: datetime) -> dict[str, Any]:
    inc = facts["incident"]
    key = inc.get("key") or str(inc.get("_id"))
    target = inc.get("target") or "unknown"
    routes = inc.get("routes", [])
    route_str = ", ".join(routes) if routes else "all"
    sli = inc.get("sli", "unknown")
    t = inc.get("t") or {}
    impact = inc.get("impact") or {}
    diag = inc.get("diagnosis") or {}
    inv = facts.get("investigation") or {}

    title = f"Postmortem: {key} ({sli} on {target}, {route_str})"
    summary = narrative.get("summary") or (
        f"Sự cố {sli} trên target {target}, route {route_str}. "
        f"Chẩn đoán: {diag.get('hypothesis', 'chưa có')} "
        f"(side={diag.get('side', 'unknown')}, confidence={float(diag.get('confidence', 0)):.0%})."
    )

    lines = [
        f"# {title}",
        "",
        f"**Target:** `{target}` · **Routes:** `{route_str}` · **SLI:** `{sli}` · "
        f"**Severity:** `{inc.get('severity', '—')}`",
        f"_Tạo lúc {_fmt_t(now)}_",
        "",
        "## 1. Tóm tắt",
        summary,
        "",
        "## 2. Tác động",
        f"- Requests bị ảnh hưởng: {int(impact.get('requests', 0)):,}",
        f"- Sessions: {int(impact.get('sessions', 0)):,}",
        f"- Delivered bad (lỗi tới client): {int(impact.get('delivered_bad', 0)):,}",
        f"- Error budget tiêu thụ: {float(impact.get('budget_consumed', 0)):.1%}",
        f"- Chi phí phát sinh: ${float(impact.get('extra_cost_usd', 0)):.2f}",
        "",
        "## 3. Timeline",
        f"- MTTD (first bad → detected): {_minutes(t.get('first_bad_at'), t.get('detected_at'))}",
        f"- MTTM (detected → mitigated): {_minutes(t.get('detected_at'), t.get('mitigated_at'))}",
        f"- MTTR (detected → resolved): {_minutes(t.get('detected_at'), t.get('resolved_at'))}",
        "",
    ]
    for e in sorted(inc.get("timeline", []), key=lambda e: str(e.get("at"))):
        ref = f" (`{e['ref']}`)" if e.get("ref") else ""
        lines.append(f"- {_fmt_t(e.get('at'))} — **{e.get('kind')}** by {e.get('actor')}{ref}")

    lines += [
        "",
        "## 4. Nguyên nhân & bằng chứng",
        f"- Side: `{diag.get('side', 'unknown')}` · chẩn đoán bởi `{diag.get('by', '—')}`",
        f"- Giả thuyết: {diag.get('hypothesis', 'chưa có')}",
    ]
    for h in inv.get("hypotheses", []):
        lines.append(f"- {h.get('id')}: {h.get('statement')} (confidence {h.get('confidence')})")
        for ev in h.get("evidence", []):
            lines.append(f"  - [{ev.get('type')}] `{ev.get('ref')}`: {ev.get('claim')}")

    lines += ["", "## 5. Hành động khắc phục"]
    actions = facts.get("actions", [])
    if not actions:
        lines.append("- Không có action nào được ghi nhận.")
    for a in actions:
        verdict = (a.get("verification") or {}).get("verdict")
        v = f" · verify: **{verdict}**" if verdict else ""
        lines.append(
            f"- `{a.get('type')}` [{a.get('state')}] params=`{json.dumps(a.get('params'), ensure_ascii=False, default=str)}`{v}"
        )

    headings = {
        "went_well": "## 6. Điều làm tốt",
        "went_poorly": "## 7. Điều cần cải thiện",
        "action_items": "## 8. Action items",
    }
    for k, heading in headings.items():
        lines += ["", heading]
        items = narrative.get(k) or []
        lines += [f"- {i}" for i in items] or ["- _(chưa có — cần bổ sung thủ công)_"]

    return {
        "_id": f"pm-{key}",
        "incident_id": key,
        "title": title,
        "summary": summary,
        "body_md": "\n".join(lines) + "\n",
        "tags": [target, sli, *routes],
        "generated_by": "cortex+llm" if narrative else "cortex",
        "created_at": now,
        "updated_at": now,
    }


async def write_postmortem(
    incident_key: str,
    db: AsyncDatabase | None = None,
    llm: LlmClient | None = None,
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Soạn postmortem cho incident đã resolved; ghi vào `postmortems` và gắn `postmortem_id`."""
    now = datetime.now(tz=UTC)
    if facts is None:
        if db is None:
            raise ValueError("either db or facts is required")
        facts = await gather(incident_key, db)

    narrative: dict[str, Any] = {}
    if llm is not None:
        with llmobs.span("workflow", "cortex.postmortem", session_id=incident_key) as s:
            try:
                narrative = await narrate(llm, facts)
            except Exception as e:
                logger.warning(
                    "Postmortem narrative failed for %s (%s); facts only", incident_key, e
                )
            llmobs.annotate(s, output_data=narrative, tags={"incident_id": incident_key})

    pm = render(facts, narrative, now)
    if db is not None:
        await db[POSTMORTEMS].update_one({"_id": pm["_id"]}, {"$set": pm}, upsert=True)
        await db[INCIDENTS].update_one(
            {"$or": [{"key": incident_key}, {"_id": incident_key}]},
            {"$set": {"postmortem_id": pm["_id"], "updated_at": now}},
        )
    logger.info("Generated postmortem %s for incident %s", pm["_id"], incident_key)
    return pm
