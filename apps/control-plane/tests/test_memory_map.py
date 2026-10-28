"""SE-8.1 — bản đồ Incident Memory: chiếu 2D signature, cụm giống nhau nằm gần nhau."""

import math
import random
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from reflex_cp.api.memory import project_2d
from reflex_cp.main import create_app
from reflex_cp.settings import Settings
from reflex_mongo.collections import ACTIONS, INCIDENTS


def _cluster(center: list[float], n: int, rng: random.Random) -> list[list[float]]:
    return [[c + rng.gauss(0, 0.05) for c in center] for _ in range(n)]


def test_projection_separates_clusters() -> None:
    rng = random.Random(1)
    a = _cluster([1.0] * 32 + [0.0] * 32, 10, rng)
    b = _cluster([0.0] * 32 + [1.0] * 32, 10, rng)
    xy = project_2d(a + b)
    assert len(xy) == 20
    ca = [sum(p[i] for p in xy[:10]) / 10 for i in (0, 1)]
    cb = [sum(p[i] for p in xy[10:]) / 10 for i in (0, 1)]
    spread = max(math.dist(p, ca) for p in xy[:10])
    assert math.dist(ca, cb) > 5 * spread
    assert project_2d(a + b) == xy  # deterministic
    assert project_2d([]) == []


@pytest.mark.asyncio
async def test_memory_map_endpoint(fake_db: Any) -> None:
    rng = random.Random(2)
    for i, vec in enumerate(_cluster([0.5] * 64, 3, rng)):
        await fake_db[INCIDENTS].insert_one(
            {
                "_id": f"i{i}",
                "key": f"INC-{i}",
                "sli": "quality",
                "status": "resolved",
                "signature": {"v": 2, "vec": vec},
            }
        )
    await fake_db[INCIDENTS].insert_one({"_id": "nosig", "key": "INC-X", "sli": "quality"})
    await fake_db[ACTIONS].insert_one(
        {
            "incident_id": "INC-0",
            "parent_action_id": None,
            "type": "shift_weight",
            "verification": {"verdict": "PASS"},
        }
    )
    app = create_app(Settings())
    app.state.db = fake_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        body = (await c.get("/api/memory/map")).json()
    assert body["method"] == "pca"
    pts = {p["key"]: p for p in body["points"]}
    assert set(pts) == {"INC-0", "INC-1", "INC-2"}
    assert pts["INC-0"]["action"] == {"type": "shift_weight", "verdict": "PASS"}
    assert pts["INC-1"]["action"] is None
