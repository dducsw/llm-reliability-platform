from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from reflex_cp.actuator.expiry import ActionExpirer

NOW = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)


class _Coll:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self.docs, self.updates = docs, []

    def find(self, *_a: Any, **_k: Any) -> "_Coll":
        return self

    def __aiter__(self):
        async def gen():
            for d in self.docs:
                yield d

        return gen()

    async def find_one(self, *_a: Any, **_k: Any) -> dict[str, Any] | None:
        return self.docs[0] if self.docs else None

    async def update_one(self, flt: Any, upd: Any) -> None:
        self.updates.append(upd)


class _Actuator:
    def __init__(self) -> None:
        self.rolled: list[str] = []

    async def rollback(self, action: Any) -> object:
        self.rolled.append(action.id)
        return object()


def _action(applied_ago_s: int, duration_s: int = 300) -> dict[str, Any]:
    return {
        "_id": "act-1",
        "incident_id": "INC-1",
        "type": "shift_weight",
        "state": "succeeded",
        "params": {"route": "r", "from": "A", "to": "B", "pct": 1.0, "duration_s": duration_s},
        "proposed_by": {"actor": "rules"},
        "execution": {
            "policy_id": "r",
            "version_before": 1,
            "version_after": 2,
            "applied_at": (NOW - timedelta(seconds=applied_ago_s)).isoformat(),
        },
    }


@pytest.mark.asyncio
async def test_expired_action_is_rolled_back() -> None:
    act = _Actuator()
    db = {"actions": _Coll([_action(400)]), "policies": _Coll([{"_id": "r", "version": 2}])}
    done = await ActionExpirer(db, act).sweep(NOW)  # type: ignore[arg-type]
    assert done == ["act-1"] and act.rolled == ["act-1"]


@pytest.mark.asyncio
async def test_unexpired_action_is_left_alone() -> None:
    act = _Actuator()
    db = {"actions": _Coll([_action(100)]), "policies": _Coll([{"_id": "r", "version": 2}])}
    assert await ActionExpirer(db, act).sweep(NOW) == []  # type: ignore[arg-type]
    assert act.rolled == []


@pytest.mark.asyncio
async def test_no_rollback_when_policy_changed_since() -> None:
    act = _Actuator()
    actions = _Coll([_action(400)])
    db = {"actions": actions, "policies": _Coll([{"_id": "r", "version": 3}])}
    assert await ActionExpirer(db, act).sweep(NOW) == []  # type: ignore[arg-type]
    assert act.rolled == [] and actions.updates
