"""Dựng "thế giới" từ attempts_ts + policy_history cho cửa sổ incident."""

from __future__ import annotations


class World:
    @classmethod
    async def load(cls, incident_key: str) -> "World":
        raise NotImplementedError
