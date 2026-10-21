import json
import random

from reflex_sim.mock_llm import outputs, profiles


def test_outputs_order_extract_valid_json() -> None:
    rng = random.Random(42)
    out = outputs.generate("order.extract", [], rng)
    data = json.loads(out)
    assert "items" in data
    assert "address" in data
    assert len(data["items"]) > 0


def test_outputs_chat_reply() -> None:
    rng = random.Random(42)
    out = outputs.generate("chat.reply", [], rng)
    assert isinstance(out, str)
    assert len(out) > 5


def test_profiles() -> None:
    prof = profiles.get_profile("large")
    assert prof.ttft_mu > 0
    assert prof.tps_mean > 0
