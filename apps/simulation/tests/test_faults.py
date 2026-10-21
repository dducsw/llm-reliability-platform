import random
from reflex_sim.chaos_proxy import injector
from reflex_sim.chaos_proxy.faults import Fault, FaultSelector, FaultType


def _sample_resp(content: str = '{"items": [{"name": "Trà sữa", "qty": 2}], "address": "123 Lê Lợi"}') -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ]
    }


def test_truncate_fault() -> None:
    fault = Fault(
        type=FaultType.TRUNCATE,
        selector=FaultSelector(target="vendorA:large"),
        params={"keep_ratio": 0.3},
    )
    rng = random.Random(42)
    original = _sample_resp()
    res = injector.apply(fault, original, rng)

    assert res["choices"][0]["finish_reason"] == "length"
    assert len(res["choices"][0]["message"]["content"]) < len(original["choices"][0]["message"]["content"])


def test_corrupt_json_fault() -> None:
    fault = Fault(
        type=FaultType.CORRUPT_JSON,
        selector=FaultSelector(target="vendorA:large"),
        params={"mode": "drop_brace"},
    )
    rng = random.Random(42)
    original = _sample_resp()
    res = injector.apply(fault, original, rng)

    content = res["choices"][0]["message"]["content"]
    assert not content.endswith("}")


def test_error_fault() -> None:
    fault = Fault(
        type=FaultType.ERROR,
        selector=FaultSelector(target="vendorA:large"),
        params={"status": 503},
    )
    res = injector.apply(fault, _sample_resp(), random.Random(42))
    assert res["status_code"] == 503
    assert "error" in res


def test_rate_limit_fault() -> None:
    fault = Fault(
        type=FaultType.RATE_LIMIT,
        selector=FaultSelector(target="vendorB:large"),
        params={"retry_after_s": 5},
    )
    res = injector.apply(fault, _sample_resp(), random.Random(42))
    assert res["status_code"] == 429
    assert res["retry_after"] == 5


def test_selector_matching() -> None:
    faults = [
        Fault(type=FaultType.TRUNCATE, selector=FaultSelector(target="vendorA:large", route="order.extract")),
        Fault(type=FaultType.ERROR, selector=FaultSelector(target="vendorB:large")),
    ]
    rng = random.Random(42)

    # Khớp target + route
    m1 = injector.select(faults, target="vendorA:large", route="order.extract", rng=rng)
    assert len(m1) == 1
    assert m1[0].type == FaultType.TRUNCATE

    # Không khớp route
    m2 = injector.select(faults, target="vendorA:large", route="chat.reply", rng=rng)
    assert len(m2) == 0

    # Khớp target chung
    m3 = injector.select(faults, target="vendorB:large", route="any.route", rng=rng)
    assert len(m3) == 1
    assert m3[0].type == FaultType.ERROR
