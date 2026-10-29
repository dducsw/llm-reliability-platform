from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from reflex_mongo.collections import (
    ACTIONS,
    HEALTH_STATE,
    INCIDENTS,
    INVESTIGATIONS,
    POLICIES,
    POLICY_HISTORY,
)
from reflex_mongo.readmodels import (
    PulseReadModel,
    WarRoomReadModel,
    get_incident,
    get_policy,
    get_policy_history,
    get_pulse,
    get_war_room,
    list_approvals,
    list_incidents,
    list_policies,
)


class AsyncCursorMock:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self.docs = docs

    def __aiter__(self):
        self._iter = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None

    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self


def make_mock_db(collections_data: dict[str, list[dict[str, Any]]]):
    db = MagicMock()

    def get_collection(name: str):
        coll = MagicMock()
        docs = collections_data.get(name, [])

        def mock_find(query=None):
            filtered = docs
            if query:
                if "is_open" in query:
                    filtered = [d for d in filtered if d.get("is_open") == query["is_open"]]
                if "state" in query and "$in" in query["state"]:
                    filtered = [d for d in filtered if d.get("state") in query["state"]["$in"]]
                if "policy_id" in query:
                    filtered = [d for d in filtered if d.get("policy_id") == query["policy_id"]]
            return AsyncCursorMock(filtered)

        async def mock_find_one(query=None):
            if not query:
                return docs[0] if docs else None
            for d in docs:
                if "key" in query and d.get("key") == query["key"]:
                    return d
                if "_id" in query and d.get("_id") == query["_id"]:
                    return d
                if "$or" in query:
                    for cond in query["$or"]:
                        for k, v in cond.items():
                            if d.get(k) == v:
                                return d
            return None

        coll.find = MagicMock(side_effect=mock_find)
        coll.find_one = AsyncMock(side_effect=mock_find_one)
        return coll

    db.__getitem__.side_effect = get_collection
    return db


@pytest.mark.asyncio
async def test_get_pulse():
    db = make_mock_db(
        {
            HEALTH_STATE: [{"_id": "target:vendorA", "status": "degraded"}],
            INCIDENTS: [{"_id": "inc-1", "is_open": True, "title": "429 storm"}],
            POLICIES: [{"_id": "chat.reply", "version": 2}],
        }
    )

    pulse = await get_pulse(db)
    assert isinstance(pulse, PulseReadModel)
    assert len(pulse.health) == 1
    assert len(pulse.incidents) == 1
    assert len(pulse.policies) == 1
    assert pulse.incidents[0]["title"] == "429 storm"


@pytest.mark.asyncio
async def test_list_and_get_incidents():
    db = make_mock_db(
        {
            INCIDENTS: [
                {"_id": "inc-1", "key": "INC-01", "is_open": True},
                {"_id": "inc-2", "key": "INC-02", "is_open": False},
            ]
        }
    )

    open_incidents = await list_incidents(db, is_open=True)
    assert len(open_incidents) == 1
    assert open_incidents[0]["key"] == "INC-01"

    inc = await get_incident(db, "INC-01")
    assert inc is not None
    assert inc["_id"] == "inc-1"


@pytest.mark.asyncio
async def test_get_war_room():
    db = make_mock_db(
        {
            INCIDENTS: [{"_id": "inc-1", "key": "INC-01", "timeline": [{"status": "DETECTED"}]}],
            ACTIONS: [{"_id": "act-1", "incident_id": "INC-01", "type": "shift_weight"}],
            INVESTIGATIONS: [{"_id": "inv-1", "incident_id": "INC-01", "root_cause": "rate_limit"}],
        }
    )

    war_room = await get_war_room(db, "INC-01")
    assert war_room is not None
    assert isinstance(war_room, WarRoomReadModel)
    assert war_room.incident["key"] == "INC-01"
    assert len(war_room.actions) == 1
    assert war_room.investigation["root_cause"] == "rate_limit"
    assert len(war_room.timeline) == 1


@pytest.mark.asyncio
async def test_list_approvals():
    db = make_mock_db(
        {
            ACTIONS: [
                {"_id": "act-1", "state": "awaiting_approval"},
                {"_id": "act-2", "state": "applied"},
                {"_id": "act-3", "state": "proposed"},
            ]
        }
    )

    approvals = await list_approvals(db)
    assert len(approvals) == 2
    ids = {a["_id"] for a in approvals}
    assert ids == {"act-1", "act-3"}


@pytest.mark.asyncio
async def test_policies_queries():
    db = make_mock_db(
        {
            POLICIES: [{"_id": "chat.reply", "version": 2}],
            POLICY_HISTORY: [
                {"_id": "h-1", "policy_id": "chat.reply", "version": 1},
                {"_id": "h-2", "policy_id": "chat.reply", "version": 2},
            ],
        }
    )

    policies = await list_policies(db)
    assert len(policies) == 1
    p = await get_policy(db, "chat.reply")
    assert p is not None
    assert p["version"] == 2

    history = await get_policy_history(db, "chat.reply")
    assert len(history) == 2
