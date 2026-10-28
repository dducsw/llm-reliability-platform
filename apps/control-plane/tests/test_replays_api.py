"""SE-8.1 — POST /api/replays xếp job, chạy nền, ghi trạng thái vào `replays`."""

import asyncio
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from reflex_cp.main import create_app
from reflex_cp.settings import Settings
from reflex_mongo.collections import INCIDENTS, REPLAYS


def _client(db: Any) -> AsyncClient:
    app = create_app(Settings())
    app.state.db = db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _wait_done(db: Any, rid: str) -> dict[str, Any]:
    for _ in range(200):
        doc = await db[REPLAYS].find_one({"_id": rid})
        if doc and doc["status"] in ("completed", "failed"):
            return doc
        await asyncio.sleep(0.02)
    raise AssertionError("replay did not finish")


@pytest.mark.asyncio
async def test_replay_job_runs_to_completion(fake_db: Any) -> None:
    await fake_db[INCIDENTS].insert_one({"_id": "i1", "key": "INC-1", "sli": "quality"})
    async with _client(fake_db) as c:
        res = await c.post(
            "/api/replays",
            json={"incident_id": "INC-1", "variants": ["naive", "reflex_recorded"], "k": 2},
        )
        assert res.status_code == 202
        rid = res.json()["_id"]
        assert res.json()["status"] == "queued"
        doc = await _wait_done(fake_db, rid)
        assert doc["status"] == "completed", doc.get("error")
        assert set(doc["variants"]) == {"naive", "reflex_recorded"}
        assert "calibration_error" in doc

        listed = (await c.get("/api/replays", params={"incident_id": "INC-1"})).json()["items"]
        assert [d["_id"] for d in listed] == [rid]
        assert (await c.get(f"/api/replays/{rid}")).json()["status"] == "completed"


@pytest.mark.asyncio
async def test_replay_rejects_unknown_variant_and_incident(fake_db: Any) -> None:
    await fake_db[INCIDENTS].insert_one({"_id": "i1", "key": "INC-1"})
    async with _client(fake_db) as c:
        bad_var = await c.post("/api/replays", json={"incident_id": "INC-1", "variants": ["yolo"]})
        assert bad_var.status_code == 422
        missing = await c.post("/api/replays", json={"incident_id": "INC-404"})
        assert missing.status_code == 404
        assert (
            await c.post("/api/replays", json={"incident_id": "INC-1", "k": 0})
        ).status_code == 422
    assert fake_db[REPLAYS].docs == []


@pytest.mark.asyncio
async def test_variants_endpoint_lists_catalog() -> None:
    async with _client(None) as c:
        ids = [v["id"] for v in (await c.get("/api/replays/variants")).json()["variants"]]
    assert "reflex_recorded" in ids and "naive" in ids
