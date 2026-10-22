"""Client Datadog API (đọc logs/spans/metrics/monitors, gửi events).

Cortex dùng scope chỉ-đọc. Mọi kết quả trả về đã strip field `chaos.*` (anti-cheat).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class DatadogApi:
    def __init__(self, api_key: str, app_key: str, site: str) -> None:
        self._api_key = api_key
        self._app_key = app_key
        self._site = site

    async def search_logs(
        self, query: str, frm: datetime, to: datetime, limit: int = 100
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def search_spans(
        self, query: str, frm: datetime, to: datetime, limit: int = 100
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def query_metrics(self, query: str, frm: datetime, to: datetime) -> dict[str, Any]:
        raise NotImplementedError

    async def get_monitor(self, monitor_id: int) -> dict[str, Any]:
        raise NotImplementedError

    async def send_event(
        self, title: str, text: str, tags: list[str], alert_type: str = "info"
    ) -> None:
        raise NotImplementedError


def strip_chaos_fields(payload: Any) -> Any:
    """Đệ quy bỏ mọi key `chaos.*` / `chaos_*` khỏi dict/list (kể cả key lồng trong tags dạng list)."""
    if isinstance(payload, dict):
        return {
            k: strip_chaos_fields(v)
            for k, v in payload.items()
            if not (isinstance(k, str) and k.startswith(("chaos.", "chaos_")))
        }
    if isinstance(payload, list):
        return [
            strip_chaos_fields(v)
            for v in payload
            if not (isinstance(v, str) and v.startswith(("chaos.", "chaos_")))
        ]
    return payload
