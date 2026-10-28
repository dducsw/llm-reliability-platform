import time
from typing import Any

import pytest
from reflex_sim.scenario import expectations


class _Coll:
    def __init__(self, doc: dict[str, Any] | None = None, rows: list[dict[str, Any]] | None = None):
        self.doc, self.rows, self.query = doc, rows or [], None

    async def find_one(self, query: dict[str, Any], _proj: Any = None) -> dict[str, Any] | None:
        self.query = query
        return self.doc

    async def aggregate(self, _pipeline: list[dict[str, Any]]):
        async def gen():
            for r in self.rows:
                yield r

        return gen()


class _Db(dict):
    pass


@pytest.mark.asyncio
async def test_without_db_everything_is_skipped_not_failed() -> None:
    res = await expectations.check([{"monitor": "M3"}, {"incident": {"route": "x"}}], time.time())
    assert [r["passed"] for r in res] == [None, None]


@pytest.mark.asyncio
async def test_incident_expectation_filters_by_route_and_source() -> None:
    coll = _Coll(doc={"key": "INC-1"})
    exp = {"incident": {"route": "order.extract", "opened_by": "sentinel"}, "within": "100s"}
    [r] = await expectations.check([exp], time.time(), db=_Db(incidents=coll))
    assert r["passed"] is True
    assert coll.query["routes"] == "order.extract" and coll.query["source"] == "sentinel"


@pytest.mark.asyncio
async def test_incident_expectation_fails_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(expectations, "POLL_INTERVAL_S", 0.01)
    exp = {"incident": {"route": "r"}, "within": "0s"}
    [r] = await expectations.check([exp], time.time(), db=_Db(incidents=_Coll(doc=None)))
    assert r["passed"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(("good", "ok"), [(995, True), (900, False)])
async def test_delivered_quality_threshold(good: int, ok: bool) -> None:
    db = _Db(sli_1m=_Coll(rows=[{"good": good, "total": 1000}]))
    exp = {
        "delivered_sli": {"route": "order.extract", "sli": "quality", "min": 0.99},
        "window": ["12m", "25m"],
    }
    [r] = await expectations.check([exp], time.time(), db=db, scale=5.0)
    assert r["passed"] is ok


@pytest.mark.asyncio
async def test_delivered_sli_without_data_fails() -> None:
    exp = {"delivered_sli": {"route": "r", "sli": "quality", "min": 0.9}, "window": ["1m", "2m"]}
    [r] = await expectations.check([exp], time.time(), db=_Db(sli_1m=_Coll(rows=[])))
    assert r["passed"] is False
