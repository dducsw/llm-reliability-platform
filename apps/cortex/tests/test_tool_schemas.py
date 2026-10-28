import pytest
from reflex_cortex.tools import mongo_tools, propose


@pytest.mark.asyncio
async def test_mongo_tools_return_digest() -> None:
    sli_res = await mongo_tools.sli_window(scope="target", key="vendorA:large", minutes=15, db=None)
    assert sli_res.ref == "sli_01"
    assert "quality_rate" in sli_res.digest

    contrib_res = await mongo_tools.top_contributors(target="vendorA:large", minutes=15, db=None)
    assert contrib_res.ref == "contrib_01"
    assert "finish_reason=length" in contrib_res.digest

    blast_res = await mongo_tools.blast_radius(incident_key="INC-20261021-0010", db=None)
    assert blast_res.ref == "blast_01"
    assert "saved_by_reflex" in blast_res.digest

    probe_res = await mongo_tools.probes_compare(target="vendorA:large", db=None)
    assert probe_res.ref == "probe_01"
    assert "direct=" in probe_res.digest


@pytest.mark.asyncio
async def test_propose_action_tool() -> None:
    action_id = await propose.propose_action(
        incident_key="INC-20261021-0010",
        action_type="shift_weight",
        params={
            "route": "order.extract",
            "from": "vendorA:large",
            "to": "vendorB:fallback",
            "pct": 1.0,
        },
        confidence=0.86,
        db=None,
    )
    assert action_id.startswith("act-")
