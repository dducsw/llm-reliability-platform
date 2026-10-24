from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from reflex_cp.api.series import sum_by_minute
from reflex_cp.main import create_app
from reflex_cp.settings import Settings

NOW = datetime.now(tz=UTC).replace(second=0, microsecond=0)


class _Cursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def __aiter__(self):  # type: ignore[no-untyped-def]
        async def gen():  # type: ignore[no-untyped-def]
            for d in self.docs:
                yield d

        return gen()


def _match(doc: dict, flt: dict) -> bool:
    for k, cond in flt.items():
        v = doc.get(k)
        if isinstance(cond, dict):
            if "$in" in cond and v not in cond["$in"]:
                return False
            if "$gte" in cond and not v >= cond["$gte"]:
                return False
        elif v != cond:
            return False
    return True


class _Coll:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def find(self, flt: dict) -> _Cursor:
        return _Cursor([d for d in self.docs if _match(d, flt)])

    async def find_one(self, flt: dict) -> dict | None:
        return next((d for d in self.docs if _match(d, flt)), None)


def _sli(scope: str, key: str, minutes_ago: int, total: int, ok: int) -> dict:
    return {
        "scope": scope,
        "key": key,
        "ts": NOW - timedelta(minutes=minutes_ago),
        "total": total,
        "ok": ok,
        "q_eligible": ok,
        "q_good": ok,
    }


def test_sum_by_minute_merges_targets_and_sorts() -> None:
    t0, t1 = NOW - timedelta(minutes=2), NOW - timedelta(minutes=1)
    out = sum_by_minute(
        [
            {"ts": t1, "total": 5, "ok": 5},
            {"ts": t0, "total": 10, "ok": 4, "q_eligible": 4, "q_good": 3},
            {"ts": t0, "total": 10, "ok": 10, "q_eligible": 10, "q_good": 10},
        ]
    )
    assert [p["ts"] for p in out] == [t0, t1]
    assert out[0] == {"ts": t0, "total": 20, "ok": 14, "q_eligible": 14, "q_good": 13}
    assert out[1]["q_good"] == 0


@pytest.mark.asyncio
async def test_dual_ledger_separates_delivered_from_provider() -> None:
    db: dict[str, Any] = {
        "policies": _Coll(
            [{"_id": "chat.reply", "candidates": [{"target": "vA:l"}, {"target": "vB:l"}]}]
        ),
        "sli_1m": _Coll(
            [
                _sli("route", "chat.reply", 3, 100, 99),
                _sli("route", "other", 3, 100, 1),
                _sli("target", "vA:l", 3, 60, 30),
                _sli("target", "vB:l", 3, 40, 40),
                _sli("target", "vC:l", 3, 999, 0),
                _sli("route", "chat.reply", 500, 100, 100),
            ]
        ),
        "policy_history": _Coll(
            [{"policy_id": "chat.reply", "version": 2, "at": NOW - timedelta(minutes=2)}]
        ),
    }
    app = create_app(Settings())
    app.state.db = db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/series/dual", params={"route": "chat.reply", "minutes": 60})
        bad = await c.get("/api/series/dual", params={"route": "x", "minutes": 1})
    body = res.json()
    assert body["targets"] == ["vA:l", "vB:l"]
    assert [(p["total"], p["ok"]) for p in body["delivered"]] == [(100, 99)]
    assert [(p["total"], p["ok"]) for p in body["provider"]] == [(100, 70)]
    assert body["events"][0]["label"] == "v3" and body["events"][0]["kind"] == "policy"
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_dual_ledger_without_db_is_empty() -> None:
    app = create_app(Settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        body = (await c.get("/api/series/dual", params={"route": "r"})).json()
    assert body["delivered"] == [] and body["provider"] == []
