"""Fixture dùng chung: `it_db` — db riêng `reflex_it` trên MONGODB_URI (integration).

Db được drop rồi tạo lại cho mỗi test → trước/sau mỗi test đều sạch, không đụng db dev.
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from dotenv import load_dotenv
from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.client import get_db, make_client

load_dotenv()

TEST_DB = "reflex_it"


@pytest.fixture()
async def it_db() -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        pytest.skip("MONGODB_URI chưa set")
    client = make_client(uri, app_name="reflex-it-test")
    await client.drop_database(TEST_DB)
    yield get_db(client, TEST_DB)
    await client.drop_database(TEST_DB)
    await client.close()
