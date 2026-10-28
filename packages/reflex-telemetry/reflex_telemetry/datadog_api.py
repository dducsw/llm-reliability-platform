"""Client Datadog API (đọc logs/spans/metrics/monitors, gửi events).

Cortex dùng scope chỉ-đọc. Mọi kết quả trả về đã strip field `chaos.*` (anti-cheat).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx


class DatadogApiError(RuntimeError):
    pass


class DatadogApi:
    def __init__(
        self,
        api_key: str,
        app_key: str,
        site: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._app_key = app_key
        self._site = site
        self._transport = transport
        self._timeout_s = timeout_s

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {"DD-API-KEY": self._api_key, "DD-APPLICATION-KEY": self._app_key}
        async with httpx.AsyncClient(
            base_url=f"https://api.{self._site}", transport=self._transport, timeout=self._timeout_s
        ) as client:
            resp = await client.request(method, path, headers=headers, **kwargs)
        if resp.status_code >= 400:
            raise DatadogApiError(f"{method} {path} -> {resp.status_code}: {resp.text[:200]}")
        return strip_chaos_fields(resp.json())

    async def search_logs(
        self, query: str, frm: datetime, to: datetime, limit: int = 100
    ) -> list[dict[str, Any]]:
        body = {
            "filter": {"query": query, "from": frm.isoformat(), "to": to.isoformat()},
            "page": {"limit": limit},
            "sort": "-timestamp",
        }
        return (await self._request("POST", "/api/v2/logs/events/search", json=body)).get(
            "data", []
        )

    async def search_spans(
        self, query: str, frm: datetime, to: datetime, limit: int = 100
    ) -> list[dict[str, Any]]:
        body = {
            "data": {
                "type": "search_request",
                "attributes": {
                    "filter": {"query": query, "from": frm.isoformat(), "to": to.isoformat()},
                    "page": {"limit": limit},
                },
            }
        }
        return (await self._request("POST", "/api/v2/spans/events/search", json=body)).get(
            "data", []
        )

    async def query_metrics(self, query: str, frm: datetime, to: datetime) -> dict[str, Any]:
        params = {"query": query, "from": int(frm.timestamp()), "to": int(to.timestamp())}
        return await self._request("GET", "/api/v1/query", params=params)

    async def get_monitor(self, monitor_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/monitor/{monitor_id}")

    async def find_monitors(self, name: str) -> list[dict[str, Any]]:
        """Monitor có tên chứa `name` (kèm `overall_state`)."""
        found = await self._request("GET", "/api/v1/monitor", params={"name": name})
        return [m for m in found if name.lower() in str(m.get("name", "")).lower()]

    async def send_event(
        self, title: str, text: str, tags: list[str], alert_type: str = "info"
    ) -> None:
        body = {"title": title, "text": text, "tags": tags, "alert_type": alert_type}
        await self._request("POST", "/api/v1/events", json=body)


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
