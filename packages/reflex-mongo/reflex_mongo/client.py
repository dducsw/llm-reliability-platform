"""AsyncMongoClient factory (pymongo async API), retryable writes, app name theo service."""

from __future__ import annotations

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase


def make_client(uri: str, app_name: str) -> AsyncMongoClient:
    raise NotImplementedError


def get_db(client: AsyncMongoClient, name: str = "reflex") -> AsyncDatabase:
    raise NotImplementedError
