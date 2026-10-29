"""Watchdog R4: incident bị Cortex bỏ rơi → rule engine propose qua đường action thường."""

from datetime import UTC, datetime, timedelta
from typing import Any

from reflex_core.actions import Action
from reflex_cp.incidents.watchdog import INVESTIGATOR, CortexWatchdog
from reflex_cp.policy_engine.decision import decide
from reflex_mongo.collections import ACTIONS, INCIDENTS, OUTBOX, POLICIES

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def _incident(key: str, status: str, age_s: float, **extra: Any) -> dict[str, Any]:
    return {
        "_id": key,
        "key": key,
        "status": status,
        "target": "vendorA:large",
        "routes": ["order.extract"],
        "sli": "quality",
        "signals": [],
        "t": {"detected_at": (NOW - timedelta(seconds=age_s)).isoformat()},
        **extra,
    }


async def _seed(fake_db: Any, *incidents: dict[str, Any]) -> CortexWatchdog:
    await fake_db[POLICIES].insert_one(
        {
            "_id": "order.extract",
            "candidates": [{"target": "vendorA:large"}, {"target": "vendorB:large"}],
        }
    )
    for inc in incidents:
        await fake_db[INCIDENTS].insert_one(inc)
    return CortexWatchdog(fake_db, unclaimed_s=60, stale_s=180)


async def test_unclaimed_detected_gets_rules_proposal(fake_db: Any) -> None:
    wd = await _seed(fake_db, _incident("INC-1", "detected", age_s=90))
    assert await wd.sweep(NOW) == ["INC-1"]

    inc = await fake_db[INCIDENTS].find_one({"key": "INC-1"})
    assert inc["status"] == "mitigating"
    assert inc["investigator"] == INVESTIGATOR
    assert inc["diagnosis"]["by"] == INVESTIGATOR
    assert inc["timeline"][-1]["kind"] == "cortex_fallback:unclaimed"

    [act] = fake_db[ACTIONS].docs
    assert act["state"] == "proposed"
    assert act["type"] == "shift_weight"
    assert act["params"]["to"] == "vendorB:large"
    assert act["proposed_by"] == {"actor": "rules", "investigation_id": None, "confidence": 0.6}

    [evt] = fake_db[OUTBOX].docs
    assert evt["kind"] == "cortex_fallback" and "reason:unclaimed" in evt["payload"]["tags"]


async def test_fresh_incidents_are_left_to_cortex(fake_db: Any) -> None:
    since = (NOW - timedelta(seconds=30)).isoformat()
    wd = await _seed(
        fake_db,
        _incident("INC-new", "detected", age_s=10),
        _incident(
            "INC-run", "investigating", age_s=300, investigator="cortex", investigating_since=since
        ),
    )
    assert await wd.sweep(NOW) == []
    assert fake_db[ACTIONS].docs == []


async def test_stale_investigation_is_taken_over_once(fake_db: Any) -> None:
    since = (NOW - timedelta(seconds=400)).isoformat()
    wd = await _seed(
        fake_db,
        _incident(
            "INC-2", "investigating", age_s=400, investigator="cortex", investigating_since=since
        ),
    )
    assert await wd.sweep(NOW) == ["INC-2"]
    # Lượt sau: incident đã `mitigating` → không propose lặp
    assert await wd.sweep(NOW + timedelta(seconds=600)) == []
    assert len(fake_db[ACTIONS].docs) == 1


async def test_legacy_claim_without_lease_uses_detected_at(fake_db: Any) -> None:
    wd = await _seed(fake_db, _incident("INC-3", "investigating", age_s=400))
    assert await wd.sweep(NOW) == ["INC-3"]


async def test_lost_race_does_not_propose(fake_db: Any) -> None:
    """Cortex claim (đổi investigating_since) ngay trước watchdog → filter không khớp."""
    since = (NOW - timedelta(seconds=400)).isoformat()
    wd = await _seed(
        fake_db,
        _incident("INC-4", "investigating", age_s=400, investigating_since=since),
    )
    doc = await fake_db[INCIDENTS].find_one({"key": "INC-4"})
    flt = wd._abandoned(dict(doc), NOW)
    assert flt is not None
    doc["investigating_since"] = NOW.isoformat()  # Cortex vừa claim lại
    assert not await wd._claim(flt[1], "stale", NOW)
    assert fake_db[ACTIONS].docs == []


async def test_rules_proposal_passes_confidence_guardrail(fake_db: Any) -> None:
    """shift_weight reversible → ngoại lệ R4: confidence 0.6 không chặn; guardrail khác vẫn chạy."""
    wd = await _seed(fake_db, _incident("INC-5", "detected", age_s=90))
    await wd.sweep(NOW)
    action = Action.model_validate(fake_db[ACTIONS].docs[0])
    decision = await decide(action, fake_db)
    conf = next(g for g in decision.guardrails if g.name == "confidence")
    assert conf.pass_ and "rules fallback" in (conf.detail or "")
