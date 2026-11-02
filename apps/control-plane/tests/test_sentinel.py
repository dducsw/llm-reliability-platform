from unittest.mock import AsyncMock, MagicMock

import pytest
from reflex_cp.incidents.service import IncidentService
from reflex_cp.sentinel.detector import Detector
from reflex_cp.sentinel.health import HealthWriter
from reflex_mongo.collections import HEALTH_STATE


@pytest.mark.asyncio
async def test_detector_opens_and_merges_incident() -> None:
    service = IncidentService(db=None)
    detector = Detector(incident_service=service)

    evaluations = [
        {
            "slo_id": "target:vendorA:large:quality",
            "scope": "target",
            "key": "vendorA:large",
            "target": "vendorA:large",
            "route": "order.extract",
            "sli": "quality",
            "burn_short": 35.0,
            "burn_long": 15.0,
            "fires": True,
        }
    ]

    # Lần 1: mở incident mới
    incidents = await detector.detect(evaluations)
    assert len(incidents) == 1
    inc1 = incidents[0]
    assert inc1["key"].startswith("INC-")
    assert inc1["status"] == "detected"
    assert len(inc1["signals"]) == 1

    # Lần 2: merge signal vào cùng incident
    evaluations[0]["burn_short"] = 40.0
    incidents2 = await detector.detect(evaluations)
    assert len(incidents2) == 1
    assert incidents2[0]["key"] == inc1["key"]
    assert len(incidents2[0]["signals"]) == 2


@pytest.mark.asyncio
async def test_health_writer_empty() -> None:
    writer = HealthWriter(db=None)
    # Không raise error
    await writer.write([])
    await writer.write([{"scope": "target", "key": "t1", "fires": False}])


@pytest.mark.asyncio
async def test_health_writer_records_budget_remaining() -> None:
    db = MagicMock()
    coll = MagicMock()
    coll.update_one = AsyncMock()
    db.__getitem__.return_value = coll

    writer = HealthWriter(db=db)
    evaluations = [
        {
            "scope": "route",
            "key": "order.extract",
            "sli": "quality",
            "burn_short": 15.0,
            "burn_long": 14.5,
            "budget_remaining": 0.42,
            "fires": True,
        },
        {
            "scope": "route",
            "key": "order.extract",
            "sli": "availability",
            "burn_short": 0.0,
            "burn_long": 0.0,
            "budget_remaining": 0.98,
            "fires": False,
        },
    ]

    await writer.write(evaluations)

    db.__getitem__.assert_called_with(HEALTH_STATE)
    coll.update_one.assert_called_once()
    args, kwargs = coll.update_one.call_args
    assert args[0] == {"_id": "route:order.extract"}
    update_doc = args[1]["$set"]
    assert update_doc["status"] == "degraded"
    assert update_doc["budget_remaining"] == {"quality": 0.42, "availability": 0.98}
    assert update_doc["burn"]["quality"]["short"] == 15.0
    assert kwargs.get("upsert") is True
