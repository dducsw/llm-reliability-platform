"""Sentinel và Datadog thấy cùng sự cố → một incident (không mitigation chồng nhau)."""

from typing import Any

import pytest
from reflex_cp.hooks.datadog import canonical_target
from reflex_cp.incidents.service import IncidentService


@pytest.mark.asyncio
async def test_datadog_signal_merges_into_sentinel_incident() -> None:
    svc = IncidentService()
    a = await svc.open_or_merge(
        signal={"source": "sentinel"},
        slo_id="target:vendorA:large:quality",
        target="vendorA:large",
        route="order.extract",
    )
    b = await svc.open_or_merge(
        signal={"source": "datadog"},
        slo_id="dd:15405616",
        target="vendorA:large",
        route="order.extract",
    )
    assert a["key"] == b["key"]
    assert [s["source"] for s in a["signals"]] == ["sentinel", "datadog"]


class _Targets:
    async def find_one(self, flt: dict[str, Any], *_a: Any) -> dict[str, Any] | None:
        import re

        rx = flt["_id"]
        for t in ("vendorA:large", "vendorB:large"):
            if re.match(rx["$regex"], t, re.IGNORECASE):
                return {"_id": t}
        return None


@pytest.mark.asyncio
async def test_lowercased_datadog_tag_maps_back_to_catalog_target() -> None:
    db = {"targets": _Targets()}
    assert await canonical_target(db, "vendora:large") == "vendorA:large"
    assert await canonical_target(db, "unknown:x") == "unknown:x"
    assert await canonical_target(db, None) is None


@pytest.mark.asyncio
async def test_route_only_signal_merges_into_open_incident_on_route() -> None:
    """M7 chỉ group theo route → không có target; vẫn phải gộp vào incident Sentinel trên route đó."""
    svc = IncidentService()
    a = await svc.open_or_merge(
        signal={"source": "sentinel"},
        slo_id="target:vendorA:large:quality",
        target="vendorA:large",
        route="order.extract",
    )
    b = await svc.open_or_merge(
        signal={"source": "datadog"}, slo_id="dd:15405615", route="order.extract"
    )
    assert a["key"] == b["key"]
