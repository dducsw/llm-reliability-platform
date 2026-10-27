"""chaos-proxy runs watcher: fault = phase mới nhất của run active; run kết thúc → hết fault."""

import asyncio
import os
from typing import Any

import pytest
from reflex_mongo.client import get_db, make_client
from reflex_mongo.collections import CHAOS_RUNS
from reflex_sim.chaos_proxy.runs_watcher import ChaosRunsWatcher

F1 = {"type": "error", "target": "vendorA:large", "params": {"rate": 0.5}}
F2 = {"type": "latency", "target": "vendorA:large", "params": {"ms": 800}}


def test_current_faults_uses_latest_phase_per_run() -> None:
    docs = [
        {"run_id": "r1", "phase_index": 0, "faults": [F1]},
        {"run_id": "r1", "phase_index": 1, "faults": [F2]},
        {"run_id": "r2", "phase_index": 0, "faults": [F1]},
    ]
    assert ChaosRunsWatcher.current_faults(docs) == [F2, F1]
    assert ChaosRunsWatcher.current_faults([]) == []


async def _until(pred: Any, timeout_s: float = 5.0) -> None:
    for _ in range(int(timeout_s / 0.05)):
        if pred():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not met")


@pytest.mark.integration
async def test_faults_cleared_when_run_completes() -> None:
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        pytest.skip("MONGODB_URI chưa set")
    client = make_client(uri, app_name="reflex-it-sim")
    db: Any = get_db(client, "reflex_it_sim")
    await db[CHAOS_RUNS].delete_many({})
    w = ChaosRunsWatcher(db)
    try:
        await w.start()
        await asyncio.sleep(0.5)
        await db[CHAOS_RUNS].insert_one(
            {"run_id": "r1", "phase_index": 0, "status": "active", "faults": [F1]}
        )
        await _until(lambda: len(w.active_faults) == 1)
        # Runner đóng run bằng update_many (event không có fullDocument)
        await db[CHAOS_RUNS].update_many({"run_id": "r1"}, {"$set": {"status": "completed"}})
        await _until(lambda: w.active_faults == [])
    finally:
        await w.stop()
        await client.drop_database("reflex_it_sim")
        await client.close()
