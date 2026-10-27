from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from reflex_core.actions import Action, ActionState
from reflex_cp.main import create_app
from reflex_cp.settings import Settings


class _Actions:
    def __init__(self, docs: dict[str, dict]) -> None:
        self.docs = docs

    async def find_one(self, flt: dict) -> dict | None:
        return self.docs.get(flt["_id"])

    async def update_one(self, flt: dict, upd: dict, **_: Any) -> None:
        self.docs[flt["_id"]].update(upd["$set"])

    async def count_documents(self, _flt: dict) -> int:
        return 0


class _NoHealth:
    async def find_one(self, _flt: dict) -> None:
        return None


class _Db(dict):
    def __init__(self, docs: dict[str, dict]) -> None:
        super().__init__(actions=_Actions(docs), health_state=_NoHealth())


class _Actuator:
    def __init__(self, fail: bool = False) -> None:
        self.fail, self.applied = fail, []

    async def apply(self, action: Action) -> None:
        if self.fail:
            raise RuntimeError("cas conflict")
        self.applied.append(action.id)
        action.state = ActionState.SUCCEEDED


def _action(state: str, params: dict | None = None) -> dict:
    now = datetime.now(tz=UTC).isoformat()
    return {
        "_id": "a1",
        "type": "shift_weight",
        "params": params or {"route": "r", "from": "A", "to": "B", "pct": 0.5},
        "state": state,
        "proposed_by": {"actor": "cortex"},
        "created_at": now,
        "updated_at": now,
    }


def _client(docs: dict[str, dict], actuator: _Actuator) -> AsyncClient:
    app = create_app(Settings())
    app.state.db = _Db(docs)
    app.state.actuator = actuator
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.asyncio
async def test_approve_records_human_decision_and_applies() -> None:
    docs, act = {"a1": _action("awaiting_approval")}, _Actuator()
    async with _client(docs, act) as c:
        res = await c.post("/api/actions/a1/approve")
    assert res.status_code == 200 and act.applied == ["a1"]
    assert docs["a1"]["state"] == "succeeded"
    assert docs["a1"]["decision"]["mode"] == "human"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["rejected", "succeeded", "executing"])
async def test_approve_refuses_illegal_transition(state: str) -> None:
    docs, act = {"a1": _action(state)}, _Actuator()
    async with _client(docs, act) as c:
        res = await c.post("/api/actions/a1/approve")
    assert res.status_code == 409 and act.applied == []
    assert docs["a1"]["state"] == state


@pytest.mark.asyncio
async def test_approve_never_overrides_schema_failure() -> None:
    docs, act = {"a1": _action("awaiting_approval", {"route": "r"})}, _Actuator()
    async with _client(docs, act) as c:
        res = await c.post("/api/actions/a1/approve")
    assert res.status_code == 422 and act.applied == []


@pytest.mark.asyncio
async def test_approve_marks_failed_when_actuator_raises() -> None:
    docs, act = {"a1": _action("awaiting_approval")}, _Actuator(fail=True)
    async with _client(docs, act) as c:
        res = await c.post("/api/actions/a1/approve")
    assert res.json()["ok"] is False and docs["a1"]["state"] == "failed"


@pytest.mark.asyncio
async def test_reject_only_from_pending_states() -> None:
    docs = {"a1": _action("awaiting_approval")}
    async with _client(docs, _Actuator()) as c:
        assert (await c.post("/api/actions/a1/reject")).status_code == 200
        assert (await c.post("/api/actions/a1/reject")).status_code == 409
