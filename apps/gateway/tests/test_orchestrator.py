import pytest
from reflex_core.policy import Candidate, CandidateRole, Policy
from reflex_gateway.engine.orchestrator import Orchestrator, RequestContext
from reflex_gateway.policy_store import PolicyStore
from reflex_gateway.target_catalog import TargetCatalog
from reflex_gateway.telemetry.queue import TelemetryQueue


@pytest.mark.asyncio
async def test_orchestrator_complete_mock() -> None:
    ps = PolicyStore(db=None)
    policy = Policy(
        _id="order.extract",
        version=1,
        candidates=[
            Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY),
        ],
    )
    ps.set(policy)

    tc = TargetCatalog(db=None)
    tq = TelemetryQueue(maxsize=100)
    orch = Orchestrator(
        policy_store=ps,
        target_catalog=tc,
        telemetry_queue=tq,
        gateway_id="gw-test",
    )

    ctx = RequestContext(
        request_id="req-123",
        route="order.extract",
        priority=1,
        session="sess-1",
        deadline_ms=5000,
    )

    result = await orch.complete(ctx, {"messages": [{"role": "user", "content": "Extract order"}]})
    assert result.request_event.request_id == "req-123"
    assert result.request_event.outcome.value == "ok"
    assert len(result.attempt_events) == 1
    assert result.attempt_events[0].kind.value == "primary"
    assert tq.qsize() == 2  # 1 attempt + 1 request


@pytest.mark.asyncio
async def test_orchestrator_retries_after_quality_fail() -> None:
    from reflex_gateway.adapters import registry
    from reflex_gateway.adapters.base import UpstreamResult

    class _Flaky:
        name = "flaky"

        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, target: dict, payload: dict, timeout_s: float) -> UpstreamResult:
            self.calls += 1
            content = "" if self.calls == 1 else "ok"
            return UpstreamResult(
                status=200,
                content=content,
                finish_reason="stop",
                tokens_in=1,
                tokens_out=1,
                latency_ms=1.0,
                ttft_ms=1.0,
                raw={"choices": [{"message": {"content": content}}]},
            )

        def stream(self, target: dict, payload: dict, timeout_s: float):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    flaky = _Flaky()
    registry._ADAPTERS["flaky"] = flaky  # type: ignore[assignment]
    try:
        ps = PolicyStore(db=None)
        ps.set(
            Policy(
                _id="chat.reply",
                version=1,
                validators=["not_empty"],
                candidates=[Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY)],
            )
        )
        tc = TargetCatalog(db=None)
        tc._targets["mock:large"] = {"_id": "mock:large", "adapter": "flaky"}
        orch = Orchestrator(policy_store=ps, target_catalog=tc, telemetry_queue=TelemetryQueue(100))
        ctx = RequestContext(
            request_id="r", route="chat.reply", priority=1, session=None, deadline_ms=5000
        )
        res = await orch.complete(ctx, {"messages": [{"role": "user", "content": "hi"}]})
    finally:
        registry._ADAPTERS.pop("flaky", None)

    assert [a.kind.value for a in res.attempt_events] == ["primary", "quality_retry"]
    assert res.request_event.outcome.value == "ok"


class _Slow:
    """Adapter giả: mỗi target có độ trễ riêng, đếm số lần bị hủy."""

    name = "slowfast"

    def __init__(self, delays: dict[str, float]) -> None:
        self.delays = delays
        self.cancelled: list[str] = []

    async def complete(self, target: dict, payload: dict, timeout_s: float):  # type: ignore[no-untyped-def]
        import asyncio

        from reflex_gateway.adapters.base import UpstreamResult

        try:
            await asyncio.sleep(self.delays[target["_id"]])
        except asyncio.CancelledError:
            self.cancelled.append(target["_id"])
            raise
        return UpstreamResult(
            status=200,
            content="ok",
            finish_reason="stop",
            tokens_in=1,
            tokens_out=1,
            latency_ms=self.delays[target["_id"]] * 1000,
            ttft_ms=1.0,
            raw={"choices": [{"message": {"content": "ok"}}]},
        )

    def stream(self, target: dict, payload: dict, timeout_s: float):  # type: ignore[no-untyped-def]
        raise NotImplementedError


def _two_target_orch(adapter: _Slow, hedge: bool, **policy_kw):  # type: ignore[no-untyped-def]
    from reflex_core.policy import HedgeConfig
    from reflex_gateway.adapters import registry

    registry._ADAPTERS["slowfast"] = adapter  # type: ignore[assignment]
    ps = PolicyStore(db=None)
    ps.set(
        Policy(
            _id="chat.reply",
            version=3,
            candidates=[
                Candidate(target="slow:a", weight=0.99, role=CandidateRole.PRIMARY),
                Candidate(target="fast:b", weight=0.01, role=CandidateRole.SECONDARY),
            ],
            hedge=HedgeConfig(enabled=hedge, max_extra_cost_ratio=1.0),
            **policy_kw,
        )
    )
    tc = TargetCatalog(db=None)
    for t in ("slow:a", "fast:b"):
        tc._targets[t] = {"_id": t, "adapter": "slowfast"}
    orch = Orchestrator(policy_store=ps, target_catalog=tc, telemetry_queue=TelemetryQueue(100))
    return orch


def _ctx(priority: int = 1) -> RequestContext:
    return RequestContext(
        request_id="r", route="chat.reply", priority=priority, session=None, deadline_ms=5000
    )


@pytest.mark.asyncio
async def test_hedge_fires_after_p95_and_faster_target_wins() -> None:
    from reflex_gateway.adapters import registry

    adapter = _Slow({"slow:a": 0.3, "fast:b": 0.01})
    try:
        orch = _two_target_orch(adapter, hedge=True)
        for _ in range(25):  # đủ mẫu để có p95 ≈ 20ms
            orch.state.record_latency("slow:a", "chat.reply", 20.0)
            orch._get_hedge_budget(
                "chat.reply", orch.policy_store.get("chat.reply")
            ).record_request()  # type: ignore[arg-type]
        res = await orch.complete(_ctx(), {"messages": []})
    finally:
        registry._ADAPTERS.pop("slowfast", None)

    assert res.request_event.hedged is True
    assert res.request_event.final_target == "fast:b"
    assert [a.kind.value for a in res.attempt_events] == ["hedge"]
    assert adapter.cancelled == ["slow:a"]


@pytest.mark.asyncio
async def test_no_hedge_without_latency_history_or_when_disabled() -> None:
    from reflex_gateway.adapters import registry

    adapter = _Slow({"slow:a": 0.05, "fast:b": 0.01})
    try:
        orch = _two_target_orch(adapter, hedge=True)
        res = await orch.complete(_ctx(), {"messages": []})  # chưa có p95
        assert res.request_event.hedged is False and adapter.cancelled == []

        orch = _two_target_orch(adapter, hedge=False)
        for _ in range(25):
            orch.state.record_latency("slow:a", "chat.reply", 1.0)
        res = await orch.complete(_ctx(), {"messages": []})
        assert res.request_event.hedged is False
    finally:
        registry._ADAPTERS.pop("slowfast", None)


@pytest.mark.asyncio
async def test_shed_returns_503_only_when_all_degraded_and_priority_low() -> None:
    from reflex_core.policy import ShedConfig
    from reflex_gateway.adapters import registry

    adapter = _Slow({"slow:a": 0.0, "fast:b": 0.0})
    try:
        orch = _two_target_orch(
            adapter, hedge=False, shed=ShedConfig(when_all_degraded_min_priority=2)
        )
        for t in ("slow:a", "fast:b"):
            for _ in range(30):
                orch.state.on_attempt(t, "chat.reply", ok=False, quality_ok=False)

        shed = await orch.complete(_ctx(priority=2), {"messages": []})
        assert shed.status == 503 and shed.retry_after_s
        assert shed.body["error"]["reflex"]["reason"] == "shed"
        assert shed.request_event.outcome.value == "shed"
        assert shed.attempt_events == [] and adapter.cancelled == []

        kept = await orch.complete(_ctx(priority=0), {"messages": []})
        assert kept.status == 200

        orch.state.on_attempt("fast:b", "chat.reply", ok=True, quality_ok=True)
        for _ in range(30):
            orch.state.on_attempt("fast:b", "chat.reply", ok=True, quality_ok=True)
        assert (await orch.complete(_ctx(priority=2), {"messages": []})).status == 200
    finally:
        registry._ADAPTERS.pop("slowfast", None)


@pytest.mark.asyncio
async def test_policy_deadline_used_and_final_error_is_not_200() -> None:
    """Không có header deadline → dùng policy.deadline_ms; mọi attempt lỗi → status lỗi thật."""
    from reflex_gateway.adapters import registry
    from reflex_gateway.adapters.base import UpstreamResult

    class _Down:
        name = "down"

        def __init__(self) -> None:
            self.timeouts: list[float] = []

        async def complete(self, target: dict, payload: dict, timeout_s: float) -> UpstreamResult:
            self.timeouts.append(timeout_s)
            return UpstreamResult(
                status=503,
                content="",
                finish_reason="error",
                tokens_in=0,
                tokens_out=0,
                latency_ms=1.0,
                ttft_ms=None,
                raw={"error": "down"},
                error_class="http_error",
            )

        def stream(self, target: dict, payload: dict, timeout_s: float):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    down = _Down()
    registry._ADAPTERS["down"] = down  # type: ignore[assignment]
    try:
        ps = PolicyStore(db=None)
        ps.set(
            Policy(
                _id="cortex.reason",
                version=1,
                deadline_ms=60000,
                candidates=[Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY)],
            )
        )
        tc = TargetCatalog(db=None)
        tc._targets["mock:large"] = {"_id": "mock:large", "adapter": "down"}
        orch = Orchestrator(policy_store=ps, target_catalog=tc, telemetry_queue=TelemetryQueue(100))
        ctx = RequestContext(
            request_id="r", route="cortex.reason", priority=0, session=None, deadline_ms=None
        )
        res = await orch.complete(ctx, {"messages": [{"role": "user", "content": "hi"}]})
    finally:
        registry._ADAPTERS.pop("down", None)

    assert down.timeouts[0] == 30.0  # min(60s policy, 30s cap) — không phải 8s mặc định
    assert res.status == 503
    assert res.request_event.outcome.value == "error"


@pytest.mark.asyncio
async def test_shed_lets_one_probe_through_so_route_can_recover() -> None:
    """Health chỉ cập nhật khi có attempt: shed tuyệt đối sẽ chặn route vĩnh viễn."""
    from datetime import UTC, datetime, timedelta

    from reflex_core.policy import ShedConfig
    from reflex_gateway.adapters import registry

    adapter = _Slow({"slow:a": 0.0, "fast:b": 0.0})
    try:
        orch = _two_target_orch(
            adapter, hedge=False, shed=ShedConfig(when_all_degraded_min_priority=2)
        )
        now = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
        orch.clock = lambda: now
        for t in ("slow:a", "fast:b"):
            for _ in range(30):
                orch.state.on_attempt(t, "chat.reply", ok=False, quality_ok=False)

        assert orch.should_shed("chat.reply", 2) is True  # bắt đầu shed
        assert orch.should_shed("chat.reply", 2) is True  # vẫn trong chu kỳ
        now += timedelta(seconds=6)
        assert orch.should_shed("chat.reply", 2) is False  # 1 request thăm dò đi qua
        assert orch.should_shed("chat.reply", 2) is True  # rồi lại shed
    finally:
        registry._ADAPTERS.pop("slowfast", None)
