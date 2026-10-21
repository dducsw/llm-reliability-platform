"""Policy store: load lúc khởi động + Change Stream hot-reload (< 1s) + file snapshot fallback.

Gateway vẫn chạy với snapshot cuối khi Mongo mất kết nối.
"""

from __future__ import annotations

from reflex_core.policy import Policy


class PolicyStore:
    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    def get(self, route: str) -> Policy | None:
        raise NotImplementedError

    @property
    def ready(self) -> bool:
        raise NotImplementedError
