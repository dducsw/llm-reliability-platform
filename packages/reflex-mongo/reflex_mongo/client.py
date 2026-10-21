"""AsyncMongoClient factory (pymongo async API), retryable writes, app name theo service."""

from __future__ import annotations

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase


def make_client(uri: str, app_name: str) -> AsyncMongoClient:
    return AsyncMongoClient(
        uri,
        appname=app_name,
        tz_aware=True,
        retryWrites=True,
        serverSelectionTimeoutMS=10_000,
    )


def get_db(client: AsyncMongoClient, name: str = "reflex") -> AsyncDatabase:
    return client.get_database(name)
