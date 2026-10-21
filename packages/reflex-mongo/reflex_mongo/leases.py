"""Leader lease (collection `leases`) để chỉ một instance chạy Sentinel tick."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from reflex_mongo.collections import LEASES

logger = logging.getLogger(__name__)


class Lease:
    def __init__(self, db: AsyncDatabase, name: str, holder: str, ttl: timedelta) -> None:
        self._db = db
        self._name = name
        self._holder = holder
        self._ttl = ttl

    async def acquire_or_renew(self) -> bool:
        """Thử lấy lease hoặc gia hạn nếu mình đang giữ hoặc lease cũ đã hết hạn."""
        now = datetime.now(tz=UTC)
        expires_at = now + self._ttl

        try:
            doc = await self._db[LEASES].find_one_and_update(
                {
                    "_id": self._name,
                    "$or": [
                        {"holder": self._holder},
                        {"expires_at": {"$lt": now}},
                    ],
                },
                {
                    "$set": {
                        "holder": self._holder,
                        "expires_at": expires_at,
                        "renewed_at": now,
                    },
                    "$setOnInsert": {
                        "acquired_at": now,
                    },
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return doc is not None and doc.get("holder") == self._holder
        except DuplicateKeyError:
            return False
        except Exception as e:
            logger.warning("Error acquiring lease %s for %s: %s", self._name, self._holder, e)
            return False

    async def release(self) -> None:
        """Nhả lease."""
        try:
            await self._db[LEASES].delete_one({"_id": self._name, "holder": self._holder})
        except Exception as e:
            logger.warning("Error releasing lease %s for %s: %s", self._name, self._holder, e)
