"""DE-1.1 (integration) — Change Stream consumer, checkpoint, and resume."""

import asyncio
from typing import Any

import pytest
from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import POLICIES, STREAM_CHECKPOINTS
from reflex_mongo.streams import StreamConsumer

pytestmark = pytest.mark.integration


async def _wait_checkpoint(db: AsyncDatabase[dict[str, Any]], consumer_id: str) -> dict[str, Any]:
    """Checkpoint ghi SAU khi handler trả về — poll thay vì đọc ngay để tránh race."""
    for _ in range(50):
        cp = await db[STREAM_CHECKPOINTS].find_one({"_id": consumer_id})
        if cp is not None:
            return cp
        await asyncio.sleep(0.1)
    raise AssertionError(f"checkpoint {consumer_id} chưa được ghi sau 5s")


async def test_stream_consumer_receives_events_and_saves_checkpoint(
    it_db: AsyncDatabase[dict[str, Any]],
) -> None:
    events: list[dict[str, Any]] = []
    received_event = asyncio.Event()

    async def _handler(change: dict[str, Any]) -> None:
        events.append(change)
        received_event.set()

    consumer = StreamConsumer(
        db=it_db,
        collection=POLICIES,
        consumer_id="test_stream_c1",
        handler=_handler,
    )

    task = asyncio.create_task(consumer.run())
    try:
        # Chờ change stream sẵn sàng
        await asyncio.sleep(0.5)

        # Ghi document mới vào collection
        doc = {"_id": "stream.route.1", "version": 1, "status": "active"}
        await it_db[POLICIES].insert_one(doc)

        # Chờ handler nhận event qua asyncio.Event
        await asyncio.wait_for(received_event.wait(), timeout=5.0)

        assert len(events) >= 1
        ev = events[0]
        assert ev.get("operationType") == "insert"
        assert ev.get("documentKey", {}).get("_id") == "stream.route.1"

        # Kiểm tra checkpoint đã được lưu vào STREAM_CHECKPOINTS
        cp = await _wait_checkpoint(it_db, "test_stream_c1")
        assert "resume_token" in cp
        assert cp["collection"] == POLICIES

    finally:
        await consumer.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _run_until(consumer: StreamConsumer, done: asyncio.Event) -> None:
    task = asyncio.create_task(consumer.run())
    try:
        await asyncio.wait_for(done.wait(), timeout=10.0)
    finally:
        await consumer.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def test_stream_consumer_resumes_from_saved_checkpoint(
    it_db: AsyncDatabase[dict[str, Any]],
) -> None:
    """Event phát sinh trong lúc consumer ngừng phải được nhận khi chạy lại cùng consumer_id."""
    seen: list[str] = []
    first_done, missed_done = asyncio.Event(), asyncio.Event()

    async def _handler(change: dict[str, Any]) -> None:
        doc_id = change.get("documentKey", {}).get("_id")
        seen.append(doc_id)
        if doc_id == "stream.route.res1":
            first_done.set()
        if doc_id == "stream.route.missed":
            missed_done.set()

    def _consumer() -> StreamConsumer:
        return StreamConsumer(
            db=it_db, collection=POLICIES, consumer_id="test_stream_c2", handler=_handler
        )

    # Lần 1: nhận res1 → checkpoint được ghi.
    async def _write_first() -> None:
        await asyncio.sleep(0.5)
        await it_db[POLICIES].insert_one({"_id": "stream.route.res1", "version": 1})

    writer = asyncio.create_task(_write_first())
    await _run_until(_consumer(), first_done)
    await writer
    await _wait_checkpoint(it_db, "test_stream_c2")

    # Consumer đang dừng: event này chỉ có thể nhận lại nhờ resume token.
    await it_db[POLICIES].insert_one({"_id": "stream.route.missed", "version": 1})

    # Lần 2: cùng consumer_id → resume_after checkpoint, nhận được event bị lỡ, không lặp res1.
    await _run_until(_consumer(), missed_done)
    assert seen.count("stream.route.res1") == 1
    assert "stream.route.missed" in seen
