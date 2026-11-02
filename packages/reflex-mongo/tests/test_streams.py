"""DE-1.1 (integration) — Change Stream consumer, checkpoint, and resume."""

import asyncio
from typing import Any

import pytest
from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import POLICIES, STREAM_CHECKPOINTS
from reflex_mongo.streams import StreamConsumer

pytestmark = pytest.mark.integration


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
        cp = await it_db[STREAM_CHECKPOINTS].find_one({"_id": "test_stream_c1"})
        assert cp is not None
        assert "resume_token" in cp
        assert cp["collection"] == POLICIES

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
    # 1. Tạo checkpoint trước
    doc1 = {"_id": "stream.route.res1", "version": 1}
    await it_db[POLICIES].insert_one(doc1)

    received_res2 = asyncio.Event()

    async def _handler2(change: dict[str, Any]) -> None:
        if change.get("documentKey", {}).get("_id") == "stream.route.res2":
            received_res2.set()

    consumer2 = StreamConsumer(
        db=it_db,
        collection=POLICIES,
        consumer_id="test_stream_c2",
        handler=_handler2,
    )

    task2 = asyncio.create_task(consumer2.run())
    try:
        await asyncio.sleep(0.5)
        # Ghi document thứ 2
        await it_db[POLICIES].insert_one({"_id": "stream.route.res2", "version": 1})

        # Chờ nhận event thứ 2
        await asyncio.wait_for(received_res2.wait(), timeout=5.0)
        assert received_res2.is_set()

        cp = await it_db[STREAM_CHECKPOINTS].find_one({"_id": "test_stream_c2"})
        assert cp is not None
        assert "resume_token" in cp

    finally:
        await consumer2.stop()
        task2.cancel()
        try:
            await task2
        except asyncio.CancelledError:
            pass
