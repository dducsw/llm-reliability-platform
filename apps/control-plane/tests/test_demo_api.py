"""SE-6.6 — /api/demo cấp time scale cho demo clock."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from reflex_cp.main import create_app
from reflex_cp.settings import Settings
from reflex_mongo.collections import CHAOS_RUNS


async def _get(db: Any) -> dict[str, Any]:
    app = create_app(Settings(reflex_profile="demo"))
    app.state.db = db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        return (await c.get("/api/demo")).json()


@pytest.mark.asyncio
async def test_demo_without_run_is_realtime(fake_db: Any) -> None:
    body = await _get(fake_db)
    assert body == {"profile": "demo", "time_scale": 1.0, "run": None}


@pytest.mark.asyncio
async def test_demo_reports_active_fast_run(fake_db: Any) -> None:
    t0 = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
    await fake_db[CHAOS_RUNS].insert_one(
        {
            "run_id": "run-1",
            "phase_index": 0,
            "scenario": "silent-brownout",
            "status": "completed",
            "starts_at": t0,
            "time_scale": 60.0,
        }
    )
    await fake_db[CHAOS_RUNS].insert_one(
        {
            "run_id": "run-1",
            "phase_index": 1,
            "scenario": "silent-brownout",
            "status": "active",
            "starts_at": t0.replace(minute=1),
            "time_scale": 60.0,
        }
    )
    body = await _get(fake_db)
    assert body["time_scale"] == 60.0
    assert body["run"]["scenario"] == "silent-brownout"
    assert body["run"]["phase_index"] == 1
    assert body["run"]["started_at"].startswith("2026-10-27T10:00")
