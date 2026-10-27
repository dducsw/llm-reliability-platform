"""Fake Mongo tối thiểu (in-memory) cho test policy engine / actuator không cần atlas-local."""

from __future__ import annotations

from typing import Any

import pytest


def _match(doc: dict[str, Any], flt: dict[str, Any]) -> bool:
    for k, cond in flt.items():
        if k == "$or":
            if not any(_match(doc, sub) for sub in cond):
                return False
            continue
        val: Any = doc
        for part in k.split("."):
            val = val.get(part) if isinstance(val, dict) else None
        if isinstance(cond, dict):
            if "$ne" in cond and val == cond["$ne"]:
                return False
            if "$in" in cond and val not in cond["$in"]:
                return False
            if "$gte" in cond and (val is None or val < cond["$gte"]):
                return False
        elif val != cond:
            return False
    return True


class _Res:
    def __init__(self, n: int) -> None:
        self.modified_count = n


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self.docs = docs

    def sort(self, key: str, direction: int = 1) -> _Cursor:
        self.docs.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self

    def __aiter__(self) -> Any:
        async def gen() -> Any:
            for d in self.docs:
                yield d

        return gen()


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    async def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs.append(dict(doc))

    async def find_one(self, flt: dict[str, Any], **_: Any) -> dict[str, Any] | None:
        return next((d for d in self.docs if _match(d, flt)), None)

    def find(self, flt: dict[str, Any] | None = None, **_: Any) -> _Cursor:
        return _Cursor([d for d in self.docs if _match(d, flt or {})])

    async def count_documents(self, flt: dict[str, Any]) -> int:
        return sum(1 for d in self.docs if _match(d, flt))

    async def update_one(self, flt: dict[str, Any], update: dict[str, Any], **_: Any) -> _Res:
        doc = await self.find_one(flt)
        if doc is None:
            return _Res(0)
        doc.update(update.get("$set", {}))
        return _Res(1)


class FakeDb:
    def __init__(self) -> None:
        self.cols: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.cols.setdefault(name, FakeCollection())


@pytest.fixture()
def fake_db() -> FakeDb:
    return FakeDb()
