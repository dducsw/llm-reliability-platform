"""Guardrails: schema, single_flight, cooldown, flap_guard, healthy_destination, capacity,
cost_ceiling, blast_radius, confidence, human_only (recovery-engine.md §3).

Guardrail cần dữ liệu (db) mà thiếu dữ liệu → pass kèm `detail`, để không chặn mitigation
chỉ vì rollup chưa kịp chạy; các luật an toàn cứng (schema, human_only, confidence) thì luôn chặn.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import (
    CATALOG,
    Action,
    ActionState,
    ActionType,
    BlastRadius,
    GuardrailResult,
    validate_params,
)
from reflex_mongo.collections import (
    ACTIONS,
    HEALTH_STATE,
    INCIDENTS,
    POLICIES,
    SLI_1M,
    TARGETS,
)

logger = logging.getLogger(__name__)

_UNHEALTHY = ("degraded", "down")
_LIVE = [
    ActionState.APPROVED,
    ActionState.EXECUTING,
    ActionState.VERIFYING,
    ActionState.SUCCEEDED,
]
_RADIUS_RANK = {
    BlastRadius.NONE: 0,
    BlastRadius.ROUTE: 1,
    BlastRadius.TARGET: 2,
    BlastRadius.SERVICE: 3,
}
# Mức radius tối đa được auto theo severity incident; không có incident → chỉ route
_RADIUS_BY_SEVERITY = {
    "critical": BlastRadius.TARGET,
    "high": BlastRadius.ROUTE,
    "warning": BlastRadius.ROUTE,
}
# Action dịch chuyển traffic sang một target đích → capacity / cost / flap áp dụng
_MOVES_TRAFFIC = (ActionType.SHIFT_WEIGHT, ActionType.FAILBACK_STEP, ActionType.DOWNGRADE_TIER)


@dataclass(frozen=True)
class GuardrailConfig:
    cooldown_s: float = 120.0
    flap_window_s: float = 900.0
    flap_max_flips: int = 3
    capacity_headroom: float = 0.8
    cost_ceiling_usd_h: float = 5.0
    load_window_s: float = 300.0
    min_confidence: float = 0.7
    budget_low: float = 0.1  # budget còn < 10% → cho phép radius cao hơn một bậc
    # R4: action của rule engine (Cortex/LLM offline) được auto nếu reversible + có hạn;
    # các guardrail còn lại (healthy_destination, capacity, blast_radius, cooldown…) vẫn chạy
    rules_auto_reversible: bool = True
    rules_max_duration_s: int = 300

    @classmethod
    def from_env(cls) -> GuardrailConfig:
        demo = os.getenv("REFLEX_PROFILE", "demo") == "demo"
        return cls(
            cooldown_s=30.0 if demo else 120.0,
            cost_ceiling_usd_h=float(os.getenv("REFLEX_COST_CEILING_USD_H", "5.0")),
            rules_auto_reversible=os.getenv("REFLEX_RULES_AUTO_REVERSIBLE", "true").lower()
            in ("1", "true", "yes"),
        )


def _ok(name: str, detail: str | None = None) -> GuardrailResult:
    return GuardrailResult(name=name, **{"pass": True}, detail=detail)


def _fail(name: str, detail: str) -> GuardrailResult:
    return GuardrailResult(name=name, **{"pass": False}, detail=detail)


def _scope(action: Action) -> tuple[str, str] | None:
    for field in ("route", "target", "service", "flag"):
        if action.params.get(field):
            return field, str(action.params[field])
    return None


def _destination(action: Action) -> str | None:
    dest = action.params.get("to") or action.params.get("to_target")
    return str(dest) if dest else None


def _moved_share(action: Action, weights: dict[str, float]) -> float:
    """Phần traffic của route sẽ chuyển sang đích (0..1)."""
    p = action.params
    if action.type == ActionType.SHIFT_WEIGHT:
        return weights.get(str(p.get("from")), 1.0) * float(p.get("pct", 0))
    if action.type == ActionType.FAILBACK_STEP:
        return max(0.0, float(p.get("pct", 0)) / 100 - weights.get(str(p.get("to")), 0.0))
    return 1.0  # downgrade_tier: cả route


async def _load(db: AsyncDatabase, scope: str, key: str, since: datetime) -> dict[str, float]:
    """Tổng sli_1m trong cửa sổ: total, cost_usd, tokens_in/out."""
    agg = {"total": 0.0, "cost_usd": 0.0, "tokens_in": 0.0, "tokens_out": 0.0}
    async for d in db[SLI_1M].find({"scope": scope, "key": key, "ts": {"$gte": since}}):
        for k in agg:
            agg[k] += float(d.get(k) or 0)
    return agg


async def _weights(db: AsyncDatabase, route: str) -> dict[str, float]:
    pol = await db[POLICIES].find_one({"_id": route})
    return {c["target"]: float(c.get("weight", 0)) for c in (pol or {}).get("candidates", [])}


async def _cooldown(
    action: Action, db: AsyncDatabase | None, cfg: GuardrailConfig
) -> GuardrailResult:
    scope = _scope(action)
    if db is None or scope is None:
        return _ok("cooldown")
    since = datetime.now(tz=UTC) - timedelta(seconds=cfg.cooldown_s)
    recent = await db[ACTIONS].find_one(
        {
            "_id": {"$ne": action.id},
            "type": action.type.value,
            f"params.{scope[0]}": scope[1],
            "state": {"$in": [s.value for s in _LIVE]},
            "created_at": {"$gte": since},
        }
    )
    if recent is not None:
        return _fail(
            "cooldown",
            f"{action.type.value} on {scope[0]}={scope[1]} within {cfg.cooldown_s:.0f}s "
            f"(action {recent.get('_id')})",
        )
    return _ok("cooldown")


async def _flap_guard(
    action: Action, db: AsyncDatabase | None, cfg: GuardrailConfig
) -> GuardrailResult:
    route = action.params.get("route")
    dest = _destination(action)
    if db is None or not route or action.type not in _MOVES_TRAFFIC or dest is None:
        return _ok("flap_guard")
    since = datetime.now(tz=UTC) - timedelta(seconds=cfg.flap_window_s)
    dests: list[str] = []
    cursor = (
        db[ACTIONS]
        .find(
            {
                "_id": {"$ne": action.id},
                "params.route": route,
                "type": {"$in": [t.value for t in _MOVES_TRAFFIC]},
                "state": {"$in": [s.value for s in _LIVE]},
                "created_at": {"$gte": since},
            }
        )
        .sort("created_at", 1)
    )
    async for d in cursor:
        p = d.get("params") or {}
        if p.get("to") or p.get("to_target"):
            dests.append(str(p.get("to") or p.get("to_target")))
    dests.append(dest)
    flips = sum(1 for a, b in pairwise(dests) if a != b)
    if flips > cfg.flap_max_flips:
        return _fail(
            "flap_guard",
            f"Route {route} flipped {flips}× in {cfg.flap_window_s / 60:.0f}m → page_human",
        )
    return _ok("flap_guard", f"{flips} flip(s) in window")


async def _healthy_destination(action: Action, db: AsyncDatabase | None) -> GuardrailResult:
    dest = _destination(action)
    if db is None or not dest:
        return _ok("healthy_destination")
    hs = await db[HEALTH_STATE].find_one({"_id": f"target:{dest}"})
    if hs is None:
        return _ok("healthy_destination", f"No health data for {dest}")
    status = hs.get("status", "unknown")
    if status in _UNHEALTHY:
        return _fail("healthy_destination", f"Destination {dest} is {status}")
    return _ok("healthy_destination")


async def _capacity_and_cost(
    action: Action, db: AsyncDatabase | None, cfg: GuardrailConfig
) -> tuple[GuardrailResult, GuardrailResult]:
    p = action.params
    route = p.get("route")
    if db is None or not route:
        return _ok("capacity"), _ok("cost_ceiling")

    since = datetime.now(tz=UTC) - timedelta(seconds=cfg.load_window_s)
    route_load = await _load(db, "route", str(route), since)
    if route_load["total"] <= 0:
        return _ok("capacity", "No recent route traffic"), _ok("cost_ceiling", "No recent traffic")
    route_rps = route_load["total"] / cfg.load_window_s
    route_cost_h = route_load["cost_usd"] * 3600 / cfg.load_window_s

    # Hedging: chi phí tăng thêm tối đa = max_cost × chi phí hiện tại của route
    if action.type == ActionType.ENABLE_HEDGING:
        delta = route_cost_h * float(p.get("max_cost", 0))
        return _ok("capacity"), _cost_result(delta, cfg)

    dest = _destination(action)
    if action.type not in _MOVES_TRAFFIC or dest is None:
        return _ok("capacity"), _ok("cost_ceiling")

    moved_rps = route_rps * _moved_share(action, await _weights(db, str(route)))
    dest_doc = await db[TARGETS].find_one({"_id": dest}) or {}

    # capacity: tải hiện có của đích + phần chuyển sang ≤ capacity_hint × headroom (S5)
    cap = dest_doc.get("capacity_hint_rps")
    if cap:
        dest_rps = (await _load(db, "target", dest, since))["total"] / cfg.load_window_s
        limit = float(cap) * cfg.capacity_headroom
        projected = dest_rps + moved_rps
        detail = f"{projected:.1f} rps → {dest} (limit {limit:.1f})"
        capacity = _ok("capacity", detail) if projected <= limit else _fail("capacity", detail)
    else:
        capacity = _ok("capacity", f"No capacity_hint for {dest}")

    # cost_ceiling: Δcost/h = request chuyển × token trung bình × chênh giá (đích − nguồn)
    src = str(p.get("from") or "")
    src_doc = await db[TARGETS].find_one({"_id": src}) if src else None
    if not dest_doc.get("price") or not src_doc or not src_doc.get("price"):
        return capacity, _ok("cost_ceiling", "No price data")
    n = route_load["total"]
    tok_in, tok_out = route_load["tokens_in"] / n, route_load["tokens_out"] / n

    def per_req(doc: dict[str, Any]) -> float:
        pr = doc["price"]
        return (tok_in * float(pr["in_per_mtok"]) + tok_out * float(pr["out_per_mtok"])) / 1e6

    delta = moved_rps * 3600 * (per_req(dest_doc) - per_req(src_doc))
    return capacity, _cost_result(delta, cfg)


def _cost_result(delta_usd_h: float, cfg: GuardrailConfig) -> GuardrailResult:
    detail = f"{delta_usd_h:+.2f}$/h vs ceiling {cfg.cost_ceiling_usd_h:.2f}$/h"
    if delta_usd_h > cfg.cost_ceiling_usd_h:
        return _fail("cost_ceiling", detail)
    return _ok("cost_ceiling", detail)


async def _blast_radius(
    action: Action, db: AsyncDatabase | None, cfg: GuardrailConfig
) -> GuardrailResult:
    spec = CATALOG.get(action.type)
    if spec is None:
        return _fail("blast_radius", "Unknown action type")
    inc: dict[str, Any] = {}
    if db is not None and action.incident_id:
        inc = (
            await db[INCIDENTS].find_one(
                {"$or": [{"key": action.incident_id}, {"_id": action.incident_id}]}
            )
            or {}
        )
    severity: str | None = inc.get("severity")
    allowed = _RADIUS_BY_SEVERITY.get(severity or "", BlastRadius.ROUTE)
    rank = _RADIUS_RANK[allowed]

    # Budget tier: route bị ảnh hưởng sắp cạn error budget → cho phép rộng hơn một bậc
    route = action.params.get("route")
    routes = [route] if route else inc.get("routes", [])
    if db is not None and routes:
        budgets: list[float] = []
        for r in routes:
            hs = await db[HEALTH_STATE].find_one({"_id": f"route:{r}"}) or {}
            budgets += [float(v) for v in (hs.get("budget_remaining") or {}).values()]
        if budgets and min(budgets) < cfg.budget_low:
            rank = min(rank + 1, _RADIUS_RANK[BlastRadius.SERVICE])

    detail = f"{spec.blast_radius.value} vs allowed rank {rank} (severity={severity or 'none'})"
    if _RADIUS_RANK[spec.blast_radius] > rank:
        return _fail("blast_radius", detail)
    return _ok("blast_radius", detail)


def _rules_bounded_reversible(action: Action, cfg: GuardrailConfig) -> bool:
    """Ngoại lệ R4 chỉ cho `actor=rules` — Cortex/LLM offline. Không cho Cortex confidence thấp,
    không cho `rules:llm_rejected` (LLM trả đề xuất sai, có thể bị injection). Action phải
    reversible, không human_only và PHẢI có `duration_s` ≤ `rules_max_duration_s` (tự hết hạn).
    Action không có thời hạn (vd shift_weight) có thể kẹt vĩnh viễn nếu không ai hoàn tác → cần duyệt.
    """
    if not cfg.rules_auto_reversible or action.proposed_by.actor != "rules":
        return False
    spec = CATALOG.get(action.type)
    if spec is None or not spec.reversible or spec.human_only:
        return False
    duration = action.params.get("duration_s")
    return duration is not None and int(duration) <= cfg.rules_max_duration_s


async def evaluate_all(
    action: Action,
    db: AsyncDatabase | None = None,
    cfg: GuardrailConfig | None = None,
) -> list[GuardrailResult]:
    """Chạy toàn bộ 10 guardrails cho action trước khi quyết định thực thi."""
    cfg = cfg or GuardrailConfig.from_env()
    results: list[GuardrailResult] = []

    # 1. Schema guardrail
    try:
        validate_params(action.type, action.params)
        results.append(_ok("schema"))
    except Exception as e:
        results.append(_fail("schema", str(e)))

    # 2. Human-only guardrail
    spec = CATALOG.get(action.type)
    if spec is not None and spec.human_only:
        results.append(_fail("human_only", "Action requires human approval"))
    else:
        results.append(_ok("human_only"))

    # 3. Confidence guardrail (action máy đề xuất: cortex / rules)
    confidence = action.proposed_by.confidence
    if confidence is None:
        confidence = action.params.get("confidence", 1.0)
    # Mọi actor không phải người (cortex, rules, rules:llm_rejected, actor lạ…) đều bị kiểm
    if action.proposed_by.actor != "human" and confidence < cfg.min_confidence:
        if _rules_bounded_reversible(action, cfg):
            results.append(
                _ok("confidence", f"rules fallback: reversible, ≤{cfg.rules_max_duration_s}s")
            )
        else:
            results.append(
                _fail("confidence", f"Confidence {confidence:.2f} < {cfg.min_confidence:.2f}")
            )
    else:
        results.append(_ok("confidence"))

    # 4. Single-flight guardrail (không có action nào khác đang executing/verifying trên cùng route)
    route = action.params.get("route")
    if db is not None and route:
        active_cnt = await db[ACTIONS].count_documents(
            {
                "_id": {"$ne": action.id},
                "params.route": route,
                "state": {"$in": [ActionState.EXECUTING, ActionState.VERIFYING]},
            }
        )
        if active_cnt == 0:
            results.append(_ok("single_flight"))
        else:
            results.append(_fail("single_flight", f"Found {active_cnt} in-flight action(s)"))
    else:
        results.append(_ok("single_flight"))

    # 5–6. Cooldown, flap guard
    results.append(await _cooldown(action, db, cfg))
    results.append(await _flap_guard(action, db, cfg))

    # 7. Healthy destination: không chuyển traffic về target đang degraded/down
    results.append(await _healthy_destination(action, db))

    # 8–9. Capacity (chặn cascading failover, S5), cost ceiling
    try:
        results.extend(await _capacity_and_cost(action, db, cfg))
    except Exception as e:
        logger.warning("capacity/cost guardrail error for %s: %s", action.id, e)
        results += [_fail("capacity", f"error: {e}"), _fail("cost_ceiling", f"error: {e}")]

    # 10. Blast radius
    results.append(await _blast_radius(action, db, cfg))

    return results
