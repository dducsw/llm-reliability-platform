import pytest
from reflex_cortex.rules import classify


def test_classify_quality_truncation() -> None:
    context_pack = {
        "incident": {
            "key": "INC-20261021-0001",
            "target": "vendorA:large",
            "routes": ["order.extract"],
            "sli": "quality",
            "signals": [{"source": "sentinel", "diagnosis": "server-side output truncation"}],
        },
        "policy": {
            "candidates": [
                {"target": "vendorA:large", "weight": 0.9},
                {"target": "vendorB:fallback", "weight": 0.1},
            ]
        },
    }

    rec = classify(context_pack)
    assert rec is not None
    assert rec.action_type == "shift_weight"
    assert rec.params["from"] == "vendorA:large"
    assert rec.params["to"] == "vendorB:fallback"
    assert rec.params["pct"] == 1.0


def test_classify_down_triggers_circuit_breaker() -> None:
    context_pack = {
        "incident": {
            "target": "vendorC:large",
            "routes": ["chat.reply"],
            "sli": "availability",
            "signals": [{"source": "datadog", "diagnosis": "provider is down (503)"}],
        }
    }
    rec = classify(context_pack)
    assert rec is not None
    assert rec.action_type == "open_circuit_global"
    assert rec.params["target"] == "vendorC:large"
