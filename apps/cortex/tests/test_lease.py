"""Lease R4: Cortex chỉ ghi diagnosis/propose khi watchdog chưa tiếp quản incident."""

from typing import Any

import pytest
from reflex_core.incident import Investigation, InvestigationStatus, Side
from reflex_cortex.agent import CortexAgent
from reflex_cortex.main import claim
from reflex_cortex.settings import Settings


class _Res:
    def __init__(self, n: int) -> None:
        self.modified_count = n


class _Col:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self.docs = docs or []

    async def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs.append(doc)

    async def update_one(self, flt: dict[str, Any], update: dict[str, Any]) -> _Res:
        flt = {k: v for k, v in flt.items() if k != "$or"}
        for d in self.docs:
            if all(d.get(k) == v for k, v in flt.items()):
                d.update(update["$set"])
                return _Res(1)
        return _Res(0)


class _Db:
    def __init__(self, incident: dict[str, Any]) -> None:
        self.cols = {"incidents": _Col([incident]), "investigations": _Col()}

    def __getitem__(self, name: str) -> _Col:
        return self.cols[name]


def _inv() -> Investigation:
    return Investigation(
        _id="inv-1",
        incident_id="INC-1",
        run_no=1,
        status=InvestigationStatus.COMPLETED,
        model="m",
        via_gateway_route="cortex.reason",
        context_pack_ref={},
    )


@pytest.mark.asyncio
async def test_claim_sets_lease_and_persist_keeps_ownership() -> None:
    db: Any = _Db({"key": "INC-1", "status": "detected"})
    lease = await claim(db, "INC-1")
    assert lease and db["incidents"].docs[0]["investigator"] == "cortex"
    agent = CortexAgent(db=db, llm=None, settings=Settings())
    assert await agent._persist(_inv(), [], Side.UNKNOWN, lease)
    assert db["incidents"].docs[0]["status"] == "mitigating"
    assert await claim(db, "INC-1") is None  # đã claim rồi → instance khác thua


@pytest.mark.asyncio
async def test_persist_after_watchdog_takeover_reports_lost() -> None:
    db: Any = _Db({"key": "INC-1", "status": "detected"})
    lease = await claim(db, "INC-1")
    db["incidents"].docs[0].update(
        {"investigator": "rules@control-plane", "investigating_since": "later"}
    )
    agent = CortexAgent(db=db, llm=None, settings=Settings())
    assert not await agent._persist(_inv(), [], Side.UNKNOWN, lease)
    assert "diagnosis" not in db["incidents"].docs[0]
    assert len(db["investigations"].docs) == 1  # vẫn lưu để audit
