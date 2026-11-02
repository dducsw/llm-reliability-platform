"""DE-0.1 (integration) — `reflex-mongo migrate` chạy lại nhiều lần không lỗi (idempotent)."""

import os

import pytest
from reflex_mongo.client import get_db, make_client
from reflex_mongo.collections import ACTIONS, BENCH_TS, INCIDENTS, POLICIES, SLI_1M
from reflex_mongo.migrate.cli import _migrate

pytestmark = pytest.mark.integration

TEST_DB = "reflex_migrate_cli_it"


async def test_migrate_cli_idempotent() -> None:
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        pytest.skip("MONGODB_URI chưa set")

    client = make_client(uri, app_name="reflex-it-migrate")
    await client.drop_database(TEST_DB)
    try:
        # Lần 1: migrate tạo mới toàn bộ collections, indexes, validators, search indexes
        await _migrate(uri, TEST_DB)
        db = get_db(client, TEST_DB)
        collections = {doc["name"] async for doc in (await db.list_collections())}

        assert INCIDENTS in collections
        assert POLICIES in collections
        assert ACTIONS in collections
        assert SLI_1M in collections
        assert BENCH_TS in collections

        # Lần 2: chạy lại trên cùng db — phải idempotent, không phát sinh ngoại lệ
        await _migrate(uri, TEST_DB)

    finally:
        await client.drop_database(TEST_DB)
        await client.close()
