"""Kiểm tra expectations (monitor state, incident, delivered_sli…) → báo cáo pass/fail."""

from __future__ import annotations

from typing import Any


async def check(expectations: list[dict[str, Any]], started_at: float) -> list[dict[str, Any]]:
    raise NotImplementedError
