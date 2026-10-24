"""Change Stream consumer với checkpoint/resume token (stream_checkpoints).

Chỉ watch collection thường (policies, health_state, incidents, actions, chaos_runs) —
Time Series không hỗ trợ Change Streams (ADR-0005).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from reflex_mongo.collections import STREAM_CHECKPOINTS

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class StreamConsumer:
    """Lắng nghe Change Stream trên collection thường và lưu checkpoint để resume không mất event."""

    def __init__(
        self,
        db: AsyncDatabase,
        collection: str,
        consumer_id: str,
        handler: Handler,
        pipeline: list[dict[str, Any]] | None = None,
    ) -> None:
        self._db = db
        self._collection = collection
        self._consumer_id = consumer_id
        self._handler = handler
        self._pipeline = pipeline or []
        self._running = False

    async def run(self) -> None:
        """Vòng lặp watch → handler → lưu resume token. Tự reconnect khi đứt kết nối."""
        self._running = True

        # Đọc resume token đã lưu từ checkpoint trước đó
        resume_token = None
        try:
            checkpoint = await self._db[STREAM_CHECKPOINTS].find_one({"_id": self._consumer_id})
            if checkpoint and "resume_token" in checkpoint:
                resume_token = checkpoint["resume_token"]
        except Exception as e:
            logger.warning("Không thể đọc resume token cho %s: %s", self._consumer_id, e)

        while self._running:
            watch_kwargs: dict[str, Any] = {}
            if resume_token:
                watch_kwargs["resume_after"] = resume_token

            try:
                async with self._db[self._collection].watch(
                    self._pipeline,
                    **watch_kwargs,
                ) as stream:
                    logger.info(
                        "Change stream started for %s (consumer: %s)",
                        self._collection,
                        self._consumer_id,
                    )
                    async for change in stream:
                        if not self._running:
                            break

                        await self._handler(change)

                        # Lưu resume token sau khi xử lý thành công
                        token = stream.resume_token or change.get("_id")
                        if token:
                            resume_token = token
                            await self._db[STREAM_CHECKPOINTS].update_one(
                                {"_id": self._consumer_id},
                                {
                                    "$set": {
                                        "resume_token": token,
                                        "collection": self._collection,
                                        "updated_at": datetime.now(tz=UTC),
                                    }
                                },
                                upsert=True,
                            )
            except asyncio.CancelledError:
                break
            except PyMongoError as err:
                logger.warning(
                    "Change stream %s gặp lỗi: %s. Thử lại sau 1s...", self._consumer_id, err
                )
                if not self._running:
                    break
                await asyncio.sleep(1.0)
            except Exception as err:
                logger.error("Lỗi không mong muốn trong stream %s: %s", self._consumer_id, err)
                if not self._running:
                    break
                await asyncio.sleep(1.0)

    async def stop(self) -> None:
        """Dừng consumer."""
        self._running = False
