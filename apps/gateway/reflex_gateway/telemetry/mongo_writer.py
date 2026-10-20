"""Background task: gom batch → insertMany(ordered=False) vào requests_ts / attempts_ts."""

from __future__ import annotations


class MongoBatchWriter:
    async def run(self) -> None:
        raise NotImplementedError

    async def flush(self) -> None:
        raise NotImplementedError
