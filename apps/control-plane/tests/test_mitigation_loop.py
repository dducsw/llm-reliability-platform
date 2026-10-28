"""Vòng verify → failback → resolve + transform failback_step + transition."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from reflex_core.actions import Action
from reflex_core.policy import Candidate, CandidateRole, default_policy
from reflex_cp.actuator.transforms import apply_action
from reflex_cp.incidents.service import IncidentService
from reflex_cp.verifier.loop import MitigationLoop
from reflex_mongo.collections import ACTIONS, INCIDENTS

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def _shift(applied_ago_s: float, **extra: Any) -> dict[str, Any]:
    return {
        "_id": "act-shift",
        "incident_id": "INC-1",
        "type": "shift_weight",
        "state": "succeeded",
        "params": {
            "route": "order.extract",
            "from": "vendorA:large",
            "to": "vendorB:large",
            "pct": 0.9,
        },
        "proposed_by": {"actor": "cortex"},
        "execution": {
            "policy_id": "order.extract",
            "version_before": 1,
            "version_after": 2,
            "applied_at": (NOW - timedelta(seconds=applied_ago_s)).isoformat(),
        },
        **extra,
    }


async def _seed(fake_db: Any, status: str, *actions: dict[str, Any]) -> MitigationLoop:
    await fake_db[INCIDENTS].insert_one(
        {
            "_id": "INC-1",
            "key": "INC-1",
            "status": status,
            "is_open": True,
            "routes": ["order.extract"],
            "t": {"detected_at": (NOW - timedelta(minutes=5)).isoformat()},
        }
    )
    for a in actions:
        await fake_db[ACTIONS].insert_one(a)
    return MitigationLoop(fake_db, verify_after_s=60, stable_s=60, min_n=20)


def test_failback_step_sets_origin_weight_and_scales_the_rest() -> None:
    pol = default_policy(
        route="r",
        candidates=[
            Candidate(target="A", weight=0.1, role=CandidateRole.PRIMARY),
            Candidate(target="B", weight=0.9, role=CandidateRole.SECONDARY),
        ],
    )
    act = Action.model_validate(
        {
            "incident_id": "INC-1",
            "type": "failback_step",
            "params": {"route": "r", "to": "A", "pct": 50},
            "proposed_by": {"actor": "failback_orchestrator"},
        }
    )
    w = {c.target: c.weight for c in apply_action(pol, act).candidates}
    assert w == {"A": 0.5, "B": 0.5}


async def test_transition_uses_valid_update_operators(fake_db: Any) -> None:
    await fake_db[INCIDENTS].insert_one({"_id": "INC-1", "key": "INC-1", "status": "mitigating"})
    await IncidentService(fake_db).transition("INC-1", "resolved", "failback")
    doc = fake_db[INCIDENTS].docs[0]
    assert doc["status"] == "resolved" and doc["is_open"] is False
    assert "$push" not in doc and doc["timeline"][0]["actor"] == "failback"


async def test_verify_pass_marks_incident_mitigated(
    fake_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    loop = await _seed(fake_db, "mitigating", _shift(120))

    async def quality(*_a: Any, **_k: Any) -> tuple[int, int]:
        return 99, 100

    monkeypatch.setattr(loop, "_quality", quality)
    assert await loop.sweep(NOW) == ["INC-1:mitigated"]
    assert fake_db[INCIDENTS].docs[0]["status"] == "mitigated"


async def test_verify_waits_for_enough_samples(
    fake_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    loop = await _seed(fake_db, "mitigating", _shift(120))

    async def quality(*_a: Any, **_k: Any) -> tuple[int, int]:
        return 5, 5  # < min_n

    monkeypatch.setattr(loop, "_quality", quality)
    assert await loop.sweep(NOW) == []
    assert fake_db[INCIDENTS].docs[0]["status"] == "mitigating"


async def test_failback_starts_when_probes_stable(
    fake_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    loop = await _seed(fake_db, "mitigated", _shift(120))

    async def stable(*_a: Any) -> bool:
        return True

    monkeypatch.setattr(loop, "_probes_stable", stable)
    assert await loop.sweep(NOW) == ["INC-1:failback_10"]
    step = fake_db[ACTIONS].docs[-1]
    assert step["type"] == "failback_step" and step["params"]["pct"] == 10
    assert step["parent_action_id"] == "act-shift" and step["state"] == "proposed"
    # step đang chờ → không đề xuất thêm
    assert await loop.sweep(NOW) == []


async def test_incident_resolves_after_final_step(fake_db: Any) -> None:
    final = {
        "_id": "act-fb100",
        "incident_id": "INC-1",
        "parent_action_id": "act-shift",
        "type": "failback_step",
        "state": "succeeded",
        "params": {"route": "order.extract", "to": "vendorA:large", "pct": 100},
        "execution": {"applied_at": (NOW - timedelta(seconds=10)).isoformat()},
    }
    loop = await _seed(fake_db, "mitigated", _shift(600), final)
    assert await loop.sweep(NOW) == ["INC-1:resolved"]
    assert fake_db[INCIDENTS].docs[0]["is_open"] is False
