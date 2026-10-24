"""Cache collection `targets` (giá, adapter, base_url, capacity_hint)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import TARGETS

logger = logging.getLogger(__name__)

_URL_ENV_DEFAULTS = {
    "CHAOS_PROXY_URL": "http://localhost:8070",
    "MOCK_LLM_URL": "http://localhost:8060",
}


def resolve_refs(doc: dict[str, Any]) -> dict[str, Any]:
    """`base_url_ref: ENV_VAR/suffix` → `base_url`; `model_ref.env_var` → `model`; key theo vendor."""
    out = dict(doc)
    ref = out.get("base_url_ref")
    if ref and not out.get("base_url"):
        env_name, _, suffix = str(ref).partition("/")
        base = os.getenv(env_name, _URL_ENV_DEFAULTS.get(env_name, "")).rstrip("/")
        out["base_url"] = f"{base}/{suffix}" if suffix else base
    env_var = (out.get("model_ref") or {}).get("env_var")
    if env_var and os.getenv(env_var):
        out.setdefault("model", os.environ[env_var])
    vendor = str(out.get("vendor", "")).upper()
    if vendor and os.getenv(f"{vendor}_API_KEY"):
        out.setdefault("api_key", os.environ[f"{vendor}_API_KEY"])
    return out


class TargetCatalog:
    def __init__(
        self, db: AsyncDatabase | None = None, seed_file: str = "seeds/targets.yaml"
    ) -> None:
        self._db = db
        self._seed_file = Path(seed_file)
        self._targets: dict[str, dict[str, Any]] = {}

    async def load(self) -> None:
        loaded = False
        if self._db is not None:
            try:
                cursor = self._db[TARGETS].find({})
                async for doc in cursor:
                    self._targets[str(doc["_id"])] = resolve_refs(doc)
                    loaded = True
            except Exception as e:
                logger.warning("Could not load targets from mongo: %s", e)

        if not loaded and self._seed_file.exists():
            try:
                raw_list = yaml.safe_load(self._seed_file.read_text(encoding="utf-8"))
                for raw in raw_list:
                    self._targets[str(raw["_id"])] = resolve_refs(raw)
                logger.info("Loaded %d targets from seed", len(self._targets))
            except Exception as e:
                logger.error("Failed to load targets from seed: %s", e)

    def get(self, target_id: str) -> dict[str, Any]:
        return self._targets.get(
            target_id,
            {
                "_id": target_id,
                "adapter": "mock",
                "vendor": "mock",
                "price": {"in_per_mtok": 0, "out_per_mtok": 0},
            },
        )
