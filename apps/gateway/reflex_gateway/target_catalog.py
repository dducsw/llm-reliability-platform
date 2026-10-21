"""Cache collection `targets` (giá, adapter, base_url, capacity_hint)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import TARGETS

logger = logging.getLogger(__name__)


class TargetCatalog:
    def __init__(self, db: AsyncDatabase | None = None, seed_file: str = "seeds/targets.yaml") -> None:
        self._db = db
        self._seed_file = Path(seed_file)
        self._targets: dict[str, dict[str, Any]] = {}

    async def load(self) -> None:
        loaded = False
        if self._db is not None:
            try:
                cursor = self._db[TARGETS].find({})
                async for doc in cursor:
                    self._targets[str(doc["_id"])] = doc
                    loaded = True
            except Exception as e:
                logger.warning("Could not load targets from mongo: %s", e)

        if not loaded and self._seed_file.exists():
            try:
                raw_list = yaml.safe_load(self._seed_file.read_text(encoding="utf-8"))
                for raw in raw_list:
                    self._targets[str(raw["_id"])] = raw
                logger.info("Loaded %d targets from seed", len(self._targets))
            except Exception as e:
                logger.error("Failed to load targets from seed: %s", e)

    def get(self, target_id: str) -> dict[str, Any]:
        return self._targets.get(
            target_id,
            {"_id": target_id, "adapter": "mock", "vendor": "mock", "price": {"in_per_mtok": 0, "out_per_mtok": 0}},
        )
