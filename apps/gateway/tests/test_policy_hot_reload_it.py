"""SE-1.5 (integration) — Change Stream thật: update policy → gateway đổi hành vi < 1s.

Bắt lỗi từng lọt qua unit test: PyMongo async cần `await coll.watch()`.
"""

import asyncio
import os
import time
from typing import Any

import pytest
from reflex_gateway.policy_store import PolicyStore
from reflex_mongo.client import get_db, make_client
from reflex_mongo.collections import POLICIES

pytestmark = pytest.mark.integration

DB = "reflex_it_gateway"
POLICY = {
    "_id": "it.route",
    "version": 1,
    "candidates": [{"target": "mock:large", "weight": 1.0, "role": "primary"}],
}


async def _wait_version(store: PolicyStore, version: int, timeout_s: float = 5.0) -> float:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_s:
        p = store.get("it.route")
        if p is not None and p.version == version:
            return time.perf_counter() - t0
        await asyncio.sleep(0.02)
    raise AssertionError(f"policy v{version} not hot-reloaded within {timeout_s}s")


async def test_policy_hot_reload_via_change_stream() -> None:
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        pytest.skip("MONGODB_URI chưa set")
    client = make_client(uri, app_name="reflex-it-gateway")
    db: Any = get_db(client, DB)
    await db[POLICIES].delete_many({})
    await db[POLICIES].insert_one(dict(POLICY))
    store = PolicyStore(db=db, seed_file="/nonexistent")
    try:
        await store.start()
        assert store.get("it.route").version == 1  # type: ignore[union-attr]
        await asyncio.sleep(0.5)  # để change stream mở xong

        await db[POLICIES].replace_one({"_id": "it.route"}, {**POLICY, "version": 2})
        assert await _wait_version(store, 2) < 1.0

        # update ($set) cũng phải reload — cần full_document="updateLookup"
        await db[POLICIES].update_one({"_id": "it.route"}, {"$set": {"version": 3}})
        assert await _wait_version(store, 3) < 1.0
    finally:
        await store.stop()
        await client.drop_database(DB)
        await client.close()
