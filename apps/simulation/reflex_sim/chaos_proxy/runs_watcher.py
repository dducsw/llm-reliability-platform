"""Watch chaos_runs (active) → cập nhật danh sách fault đang áp dụng."""

from __future__ import annotations


class ChaosRunsWatcher:
    async def run(self) -> None:
        raise NotImplementedError
