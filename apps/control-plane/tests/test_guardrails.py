import pytest
from reflex_core.actions import (
    Action,
    ActionState,
    ActionType,
    PageHumanParams,
    ProposedBy,
    ShiftWeightParams,
)
from reflex_cp.policy_engine.decision import decide
from reflex_cp.policy_engine.guardrails import evaluate_all


@pytest.mark.asyncio
async def test_guardrails_pass_auto() -> None:
    action = Action(
        type=ActionType.SHIFT_WEIGHT,
        params=ShiftWeightParams(
            route="order.extract",
            **{"from": "vendorA:large"},
            to="vendorB:fallback",
            pct=1.0,
        ).model_dump(by_alias=True),
        proposed_by=ProposedBy(actor="cortex"),
    )
    guardrails = await evaluate_all(action, db=None)
    assert all(g.pass_ for g in guardrails)

    decision = await decide(action, db=None)
    assert decision.mode == "auto"
    assert action.state == ActionState.APPROVED


@pytest.mark.asyncio
async def test_guardrail_human_only_requires_human() -> None:
    action = Action(
        type=ActionType.PAGE_HUMAN,
        params=PageHumanParams(reason="Manual intervention needed").model_dump(),
        proposed_by=ProposedBy(actor="cortex"),
    )
    guardrails = await evaluate_all(action, db=None)
    human_g = next(g for g in guardrails if g.name == "human_only")
    assert human_g.pass_ is False

    decision = await decide(action, db=None)
    assert decision.mode == "human"
    assert action.state == ActionState.AWAITING_APPROVAL


# --- SE-5.2: bảng pass/fail cho các guardrail cần dữ liệu ---------------------

from datetime import UTC, datetime, timedelta  # noqa: E402
from typing import Any  # noqa: E402

from reflex_cp.policy_engine.guardrails import GuardrailConfig  # noqa: E402
from reflex_mongo.collections import (  # noqa: E402
    ACTIONS,
    HEALTH_STATE,
    INCIDENTS,
    POLICIES,
    SLI_1M,
    TARGETS,
)

CFG = GuardrailConfig(cooldown_s=30, cost_ceiling_usd_h=5.0)


def _ago(minutes: float) -> datetime:
    return datetime.now(tz=UTC) - timedelta(minutes=minutes)


def _shift(pct: float = 0.5, to: str = "B", **kw: Any) -> Action:
    return Action(
        _id="new",
        type=ActionType.SHIFT_WEIGHT,
        params={"route": "r", "from": "A", "to": to, "pct": pct},
        proposed_by=ProposedBy(actor="cortex", confidence=0.9),
        **kw,
    )


async def _result(action: Action, db: Any, name: str) -> Any:
    return next(g for g in await evaluate_all(action, db, CFG) if g.name == name)


async def _seed_traffic(db: Any, route_rps: float, dest_rps: float = 0.0) -> None:
    """5 phút sli_1m; token mỗi request 1000 in / 500 out."""
    for m in range(5):
        ts = _ago(m)
        n = route_rps * 60
        await db[SLI_1M].insert_one(
            {
                "scope": "route",
                "key": "r",
                "ts": ts,
                "total": n,
                "cost_usd": n * 0.01,
                "tokens_in": n * 1000,
                "tokens_out": n * 500,
            }
        )
        await db[SLI_1M].insert_one(
            {"scope": "target", "key": "B", "ts": ts, "total": dest_rps * 60}
        )
    await db[POLICIES].insert_one(
        {"_id": "r", "candidates": [{"target": "A", "weight": 1.0}, {"target": "B", "weight": 0.0}]}
    )


async def _seed_targets(db: Any, cap_b: float = 30, price_b: float = 3.0) -> None:
    await db[TARGETS].insert_one(
        {"_id": "A", "capacity_hint_rps": 30, "price": {"in_per_mtok": 3.0, "out_per_mtok": 15.0}}
    )
    await db[TARGETS].insert_one(
        {
            "_id": "B",
            "capacity_hint_rps": cap_b,
            "price": {"in_per_mtok": price_b, "out_per_mtok": price_b * 5},
        }
    )


def _prior(
    to: str, minutes_ago: float, state: str = "succeeded", type_: str = "shift_weight"
) -> dict:
    return {
        "_id": f"p-{to}-{minutes_ago}",
        "type": type_,
        "params": {"route": "r", "from": "X", "to": to, "pct": 0.5},
        "state": state,
        "ago_min": minutes_ago,  # created_at tính lúc insert, không lúc collect
    }


async def _insert(db: Any, prior: dict) -> None:
    doc = {k: v for k, v in prior.items() if k != "ago_min"}
    await db[ACTIONS].insert_one({**doc, "created_at": _ago(prior["ago_min"])})


@pytest.mark.parametrize(
    ("prior", "passed"),
    [
        (None, True),
        (_prior("B", 0.2), False),  # 12s trước → trong cooldown 30s
        (_prior("B", 1.0), True),  # 60s trước → hết cooldown
        (_prior("B", 0.2, state="rejected"), True),  # bị từ chối không tính
        (_prior("B", 0.2, type_="enable_hedging"), True),  # khác action type
    ],
)
async def test_cooldown(fake_db: Any, prior: dict | None, passed: bool) -> None:
    if prior:
        await _insert(fake_db, prior)
    assert (await _result(_shift(), fake_db, "cooldown")).pass_ is passed


@pytest.mark.parametrize(
    ("history", "passed"),
    [
        (["B", "A", "B"], True),  # + B mới → 3 lần đổi chiều: vẫn cho
        (["A", "B", "A", "B"], True),  # + B (trùng chiều cuối) → vẫn 3 lần
        (["B", "A", "B", "A"], False),  # + B → 4 lần đổi chiều > 3
        (["B", "B", "B", "B"], True),
    ],
)
async def test_flap_guard(fake_db: Any, history: list[str], passed: bool) -> None:
    for i, to in enumerate(history):
        await _insert(fake_db, _prior(to, 14 - i))
    assert (await _result(_shift(to="B"), fake_db, "flap_guard")).pass_ is passed


async def test_flap_guard_ignores_actions_outside_window(fake_db: Any) -> None:
    for i, to in enumerate(["B", "A", "B", "A"]):
        await _insert(fake_db, _prior(to, 30 + i))
    assert (await _result(_shift(to="B"), fake_db, "flap_guard")).pass_ is True


@pytest.mark.parametrize(
    ("route_rps", "dest_rps", "cap_b", "passed"),
    [
        (10, 5, 30, True),  # 5 + 10×1.0×0.5 = 10 ≤ 24
        (40, 5, 30, False),  # 5 + 20 = 25 > 24 → chặn cascading failover (S5)
        (10, 20, 30, False),  # đích đã gần đầy: 20 + 5 = 25 > 24
    ],
)
async def test_capacity(
    fake_db: Any, route_rps: float, dest_rps: float, cap_b: float, passed: bool
) -> None:
    await _seed_traffic(fake_db, route_rps, dest_rps)
    await _seed_targets(fake_db, cap_b=cap_b)
    assert (await _result(_shift(), fake_db, "capacity")).pass_ is passed


async def test_capacity_passes_without_data(fake_db: Any) -> None:
    g = await _result(_shift(), fake_db, "capacity")
    assert g.pass_ is True and "No recent" in (g.detail or "")


@pytest.mark.parametrize(
    ("price_b", "passed"),
    [
        (3.0, True),  # cùng giá → Δ = 0
        (0.25, True),  # rẻ hơn → Δ âm
        (6.0, False),  # 5 rps × 3600 × (+0.0105$) ≈ +189$/h > 5$/h
    ],
)
async def test_cost_ceiling(fake_db: Any, price_b: float, passed: bool) -> None:
    await _seed_traffic(fake_db, 10)
    await _seed_targets(fake_db, cap_b=1000, price_b=price_b)
    assert (await _result(_shift(), fake_db, "cost_ceiling")).pass_ is passed


async def test_cost_ceiling_hedging_uses_route_cost(fake_db: Any) -> None:
    await _seed_traffic(fake_db, 10)  # 0.1$/s = 360$/h
    hedge = Action(
        type=ActionType.ENABLE_HEDGING,
        params={"route": "r", "max_cost": 0.05},  # +18$/h
        proposed_by=ProposedBy(actor="cortex", confidence=0.9),
    )
    assert (await _result(hedge, fake_db, "cost_ceiling")).pass_ is False


def _circuit(incident_id: str | None = None) -> Action:
    return Action(
        type=ActionType.OPEN_CIRCUIT_GLOBAL,
        params={"target": "A", "duration_s": 60},
        proposed_by=ProposedBy(actor="cortex", confidence=0.9),
        incident_id=incident_id,
    )


@pytest.mark.parametrize(
    ("severity", "action_fn", "passed"),
    [
        (None, _shift, True),  # route ≤ route
        (None, _circuit, False),  # target > route khi không có incident
        ("high", _circuit, False),
        ("critical", _circuit, True),  # critical cho phép tới target
    ],
)
async def test_blast_radius(
    fake_db: Any, severity: str | None, action_fn: Any, passed: bool
) -> None:
    if severity:
        await fake_db[INCIDENTS].insert_one({"key": "INC-1", "severity": severity})
    action = action_fn(incident_id="INC-1" if severity else None)
    assert (await _result(action, fake_db, "blast_radius")).pass_ is passed


async def test_blast_radius_low_budget_widens_one_tier(fake_db: Any) -> None:
    await fake_db[INCIDENTS].insert_one({"key": "INC-1", "severity": "critical", "routes": ["r"]})
    await fake_db[HEALTH_STATE].insert_one(
        {"_id": "route:r", "budget_remaining": {"quality": 0.05}}
    )
    shed = Action(
        type=ActionType.SHED_PRIORITY,
        params={"min_priority": 2},
        proposed_by=ProposedBy(actor="cortex", confidence=0.9),
        incident_id="INC-1",
    )
    # service > target, nhưng budget cạn → được nâng một bậc
    assert (await _result(shed, fake_db, "blast_radius")).pass_ is True


async def test_all_ten_guardrails_reported(fake_db: Any) -> None:
    names = [g.name for g in await evaluate_all(_shift(), fake_db, CFG)]
    assert len(names) == len(set(names)) == 10
