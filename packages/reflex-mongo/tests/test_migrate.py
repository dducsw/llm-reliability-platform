"""DE-0.1 - DoD: `migrate` chạy lại nhiều lần không lỗi và tạo đúng schema (data model §2-§6)."""

from pathlib import Path

import pytest
from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import ATTEMPTS_TS, BENCH_TS, DAY_S, INCIDENTS, SLI_1M
from reflex_mongo.migrate.collections import ensure_collections
from reflex_mongo.migrate.indexes import ensure_indexes
from reflex_mongo.migrate.validators import apply_validators

pytestmark = pytest.mark.integration

VALIDATOR_DIR = Path("infra/mongo/validators")


async def _collections_of(db: AsyncDatabase) -> dict[str, dict]:
    return {doc["name"]: doc async for doc in (await db.list_collections())}


async def _index_of(db: AsyncDatabase, collection: str, name: str) -> dict:
    cursor = await db[collection].list_indexes()
    return {ix["name"]: ix async for ix in cursor}[name]


async def test_migrate_idempotent(it_db: AsyncDatabase) -> None:
    for _ in range(2):  # chạy 2 lần không lỗi
        await ensure_collections(it_db)
        await ensure_indexes(it_db)
    names = set(await _collections_of(it_db))
    assert BENCH_TS in names and INCIDENTS in names and SLI_1M in names


async def test_time_series_options(it_db: AsyncDatabase) -> None:
    await ensure_collections(it_db)
    collections = await _collections_of(it_db)
    bench = collections[BENCH_TS]["options"]["timeseries"]
    assert bench["granularity"] == "hours"
    assert bench["timeField"] == "ts" and bench["metaField"] == "meta"
    assert (
        collections[BENCH_TS]["options"].get("expireAfterSeconds") is None
    )  # reference, không TTL
    assert collections[ATTEMPTS_TS]["options"]["expireAfterSeconds"] == 14 * DAY_S


async def test_key_indexes(it_db: AsyncDatabase) -> None:
    await ensure_collections(it_db)
    await ensure_indexes(it_db)
    dedup = await _index_of(it_db, INCIDENTS, "dedup_key_1")
    assert dedup["unique"] is True
    assert dedup["partialFilterExpression"] == {"is_open": True}  # chỉ incident đang mở
    sli = await _index_of(it_db, SLI_1M, "scope_1_key_1_env_1_ts_1")
    assert sli["unique"] is True
    ttl = await _index_of(it_db, SLI_1M, "ts_1")
    assert ttl["expireAfterSeconds"] == 45 * DAY_S


async def test_validators_applied_without_defs_error(it_db: AsyncDatabase) -> None:
    await ensure_collections(it_db)
    results = await apply_validators(it_db, VALIDATOR_DIR)
    assert results.get("actions") == "ok"
    assert results.get("incidents") == "ok"
    assert results.get("policies") == "ok"
