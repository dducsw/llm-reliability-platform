"""Vòng lặp Sentinel (chỉ chạy khi giữ lease)."""

from __future__ import annotations


class Sentinel:
    async def run(self) -> None:
        raise NotImplementedError
