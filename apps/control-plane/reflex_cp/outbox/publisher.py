from __future__ import annotations


class OutboxPublisher:
    async def run(self) -> None:
        raise NotImplementedError
