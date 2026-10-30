from datetime import datetime
from typing import Any

import pytest
from reflex_cp.incidents.service import IncidentService


class _Coll:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    async def find_one(self, *_a: Any, **_k: Any) -> None:
        return None

    async def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs.append(doc)


@pytest.mark.asyncio
async def test_new_incident_times_are_datetimes_so_they_sort_with_seed_data() -> None:
    coll = _Coll()
    svc = IncidentService(db={"incidents": coll})  # type: ignore[arg-type]
    await svc.open_or_merge(signal={"source": "sentinel"}, slo_id="route:r:quality", route="r")
    t = coll.docs[0]["t"]
    assert isinstance(t["detected_at"], datetime) and isinstance(t["first_bad_at"], datetime)


@pytest.mark.asyncio
async def test_new_incident_has_created_at_for_scenario_expectations() -> None:
    coll = _Coll()
    svc = IncidentService(db={"incidents": coll})  # type: ignore[arg-type]
    await svc.open_or_merge(signal={"source": "sentinel"}, slo_id="route:r:quality", route="r")
    assert isinstance(coll.docs[0]["created_at"], datetime)


class _Statsd:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def increment(self, name: str, tags: list[str]) -> None:
        self.calls.append((name, tags))


@pytest.mark.asyncio
async def test_new_incident_emits_open_metric_by_source() -> None:
    sd = _Statsd()
    svc = IncidentService(db={"incidents": _Coll()})  # type: ignore[arg-type]
    svc.statsd = sd  # type: ignore[misc]
    await svc.open_or_merge(signal={"source": "datadog"}, slo_id="route:r:quality", route="r")
    assert sd.calls == [
        ("reflex.incident.signal", ["source:datadog"]),
        ("reflex.incident.open", ["source:datadog"]),
    ]
