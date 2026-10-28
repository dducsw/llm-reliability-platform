"""Prober phát `reflex.probe.result` để Datadog có P_direct / P_via_gw (M6, M9, M10)."""

from datetime import UTC, datetime

from reflex_core.events import AttemptOutcome, ProbeEvent, ProbeMeta, ProbePath, QualityResult
from reflex_sim.prober.prober import Prober


class _Statsd:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def increment(self, name: str, tags: list[str]) -> None:
        self.calls.append((name, tags))


def _event(passed: bool, path: ProbePath) -> ProbeEvent:
    return ProbeEvent(
        ts=datetime(2026, 10, 28, tzinfo=UTC),
        meta=ProbeMeta(target="vendorA:large", path=path, env="local"),
        golden_id="g1",
        outcome=AttemptOutcome.OK if passed else AttemptOutcome.QUALITY_FAIL,
        latency_ms=5.0,
        ttft_ms=1.0,
        quality=QualityResult(pass_=passed),
        http_status=200,
    )


def test_probe_result_is_tagged_by_target_path_and_result() -> None:
    sd = _Statsd()
    p = Prober(statsd=sd)
    p.emit(_event(True, ProbePath.DIRECT), "order.extract")
    p.emit(_event(False, ProbePath.VIA_GATEWAY), "order.extract")
    (n1, t1), (_, t2) = sd.calls
    assert n1 == "reflex.probe.result"
    assert {"target:vendorA:large", "path:direct", "result:pass"} <= set(t1)
    assert {"path:via_gateway", "result:fail"} <= set(t2)


def test_prober_without_statsd_is_silent() -> None:
    Prober().emit(_event(True, ProbePath.DIRECT), "r")  # không lỗi
