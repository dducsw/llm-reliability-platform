"""Lưu incident đã resolved vào Incident Memory (signature + root cause + action hiệu quả)."""

from __future__ import annotations


async def remember(incident_key: str) -> None:
    raise NotImplementedError
