from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
import pytest
from reflex_cp.main import create_app
from reflex_cp.outbox.publisher import OutboxPublisher
from reflex_cp.settings import Settings


def _client(**settings) -> AsyncClient:  # type: ignore[no-untyped-def]
    return AsyncClient(
        transport=ASGITransport(app=create_app(Settings(**settings))), base_url="http://t"
    )


@pytest.mark.asyncio
async def test_console_token_is_enforced_when_configured() -> None:
    async with _client(reflex_console_token="s3cret") as c:
        assert (await c.get("/api/slos")).status_code == 401
        assert (
            await c.get("/api/slos", headers={"Authorization": "Bearer nope"})
        ).status_code == 401
        assert (
            await c.get("/api/slos", headers={"Authorization": "Bearer s3cret"})
        ).status_code == 200
        assert (await c.get("/healthz")).status_code == 200


@pytest.mark.asyncio
async def test_no_token_configured_allows_local_dev() -> None:
    async with _client() as c:
        assert (await c.get("/api/slos")).json() == {"slos": []}


@pytest.mark.asyncio
async def test_pipelines_expose_registry_metadata() -> None:
    async with _client() as c:
        listing = (await c.get("/api/pipelines")).json()["pipelines"]
        assert len(listing) == 18
        a4 = (await c.get("/api/pipelines/A4")).json()
        assert a4["collection"] == "sli_1m" and "def build" in a4["source"]
        assert (await c.get("/api/pipelines/A99")).status_code == 404


@pytest.mark.asyncio
async def test_lab_rejects_unknown_scenario_and_requires_token() -> None:
    async with _client(reflex_lab_token="lab") as c:
        assert (await c.post("/api/lab/scenarios/silent-brownout/run")).status_code == 401
        res = await c.post(
            "/api/lab/scenarios/../etc/passwd/run", headers={"Authorization": "Bearer lab"}
        )
        assert res.status_code == 404
        res = await c.post("/api/lab/scenarios/nope/run", headers={"Authorization": "Bearer lab"})
        assert res.status_code == 404


class _FakeOutbox:
    """Chỉ đủ cho OutboxPublisher: find_one_and_update + update_one trên list doc."""

    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    async def find_one_and_update(self, flt: dict, upd: dict) -> dict | None:
        now = flt["next_at"]["$lte"]
        for d in self.docs:
            if d["status"] == flt["status"] and d["next_at"] <= now:
                before = dict(d)
                d.update(upd["$set"])
                d["attempts"] = d.get("attempts", 0) + upd["$inc"]["attempts"]
                return before
        return None

    async def update_one(self, flt: dict, upd: dict) -> None:
        next(d for d in self.docs if d["_id"] == flt["_id"]).update(upd["$set"])


class _FakeDb(dict):
    def __init__(self, docs: list[dict]) -> None:
        super().__init__(outbox=_FakeOutbox(docs))


class _Dd:
    def __init__(self, fail: bool = False) -> None:
        self.fail, self.events = fail, []

    async def send_event(self, **kw) -> None:  # type: ignore[no-untyped-def]
        if self.fail:
            raise RuntimeError("boom")
        self.events.append(kw)


def _doc(**kw) -> dict:  # type: ignore[no-untyped-def]
    return {
        "_id": "o1",
        "status": "pending",
        "attempts": 0,
        "next_at": datetime.now(tz=UTC) - timedelta(1),
        "payload": {"title": "t", "tags": ["a:b"]},
        **kw,
    }


@pytest.mark.asyncio
async def test_outbox_publishes_then_marks_sent() -> None:
    docs, dd = [_doc()], _Dd()
    pub = OutboxPublisher(_FakeDb(docs), dd)  # type: ignore[arg-type]
    assert await pub.process_once() is True
    assert docs[0]["status"] == "sent" and dd.events[0]["title"] == "t"
    assert await pub.process_once() is False


@pytest.mark.asyncio
async def test_outbox_failure_reschedules_then_gives_up() -> None:
    docs = [_doc()]
    pub = OutboxPublisher(_FakeDb(docs), _Dd(fail=True))  # type: ignore[arg-type]
    await pub.process_once()
    assert docs[0]["status"] == "pending" and docs[0]["next_at"] > datetime.now(tz=UTC)
    docs[0].update(attempts=4, next_at=datetime.now(tz=UTC) - timedelta(1))
    await pub.process_once()
    assert docs[0]["status"] == "failed"
