"""Attempt loop: router.decide → adapter.call → validators → retry/rescue/hedge → events."""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from reflex_core.breaker import BreakerState, CircuitBreaker
from reflex_core.events import (
    AttemptEvent,
    AttemptKind,
    AttemptMeta,
    AttemptOutcome,
    QualityResult,
    RequestEvent,
    RequestMeta,
    RequestOutcome,
)
from reflex_core.hedge import HedgeBudget, hedge_delay_ms, should_shed
from reflex_core.ids import Clock, Rng
from reflex_core.policy import BreakerConfig, Policy
from reflex_core.retry import FailureClass, RetryBudget, classify
from reflex_core.routing import TargetInputs, decide
from reflex_core.validators.base import NormalizedResponse
from reflex_core.validators.registry import build_chain, run_chain
from reflex_telemetry import llmobs

from reflex_gateway.adapters.base import UpstreamResult
from reflex_gateway.adapters.registry import get_adapter
from reflex_gateway.engine.deadline import Deadline
from reflex_gateway.engine.local_state import LocalState
from reflex_gateway.policy_store import PolicyStore
from reflex_gateway.target_catalog import TargetCatalog
from reflex_gateway.telemetry import metrics, spans
from reflex_gateway.telemetry.queue import TelemetryQueue


@dataclass(slots=True)
class RequestContext:
    request_id: str
    route: str
    priority: int
    session: str | None
    deadline_ms: int | None  # None → theo policy.deadline_ms của route
    trace_id: str | None = None


DEGRADED_HEALTH = 0.5
SHED_RETRY_AFTER_S = 5


@dataclass(slots=True)
class OrchestratorResult:
    body: dict
    request_event: RequestEvent
    attempt_events: list[AttemptEvent]
    status: int = 200
    retry_after_s: int | None = None


class SystemRng:
    def random(self) -> float:
        return random.random()

    def uniform(self, a: float, b: float) -> float:
        return random.uniform(a, b)


def utc_clock() -> datetime:
    return datetime.now(tz=UTC)


class Orchestrator:
    def __init__(
        self,
        policy_store: PolicyStore,
        target_catalog: TargetCatalog,
        telemetry_queue: TelemetryQueue,
        gateway_id: str = "gw-1",
        env: str = "local",
        clock: Clock = utc_clock,
        rng: Rng | None = None,
    ) -> None:
        self.policy_store = policy_store
        self.target_catalog = target_catalog
        self.telemetry_queue = telemetry_queue
        self.gateway_id = gateway_id
        self.env = env
        self.clock = clock
        self.rng = rng or SystemRng()
        self.state = LocalState()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._retry_budgets: dict[str, RetryBudget] = {}
        self._hedge_budgets: dict[str, HedgeBudget] = {}

    def _get_breaker(self, target_id: str, config: BreakerConfig) -> CircuitBreaker:
        if target_id not in self._breakers:
            self._breakers[target_id] = CircuitBreaker(config, clock=self.clock)
        return self._breakers[target_id]

    def _get_retry_budget(self, route: str, policy: Policy) -> RetryBudget:
        if route not in self._retry_budgets:
            self._retry_budgets[route] = RetryBudget(policy.retry, clock=self.clock)
        return self._retry_budgets[route]

    def _get_hedge_budget(self, route: str, policy: Policy) -> HedgeBudget:
        if route not in self._hedge_budgets:
            self._hedge_budgets[route] = HedgeBudget(policy.hedge, clock=self.clock)
        budget = self._hedge_budgets[route]
        budget.configure(policy.hedge)
        return budget

    def _candidate_inputs(self, policy: Policy, route: str) -> dict[str, TargetInputs]:
        local = self.state.router_inputs(route)
        inputs: dict[str, TargetInputs] = {}
        for cand in policy.candidates:
            t_info = self.target_catalog.get(cand.target)
            breaker = self._get_breaker(cand.target, policy.breaker)
            is_open = breaker.state == BreakerState.OPEN
            inputs[cand.target] = TargetInputs(
                target=cand.target,
                health=0.0 if is_open else local.get(cand.target, {}).get("health", 1.0),
                budget_headroom=1.0,
                quality=local.get(cand.target, {}).get("quality", 1.0),
                cost=0.5,
                capacity=1.0,
                breaker_open=is_open,
                eligible=t_info.get("enabled", True),
            )
        return inputs

    def should_shed(self, route: str, priority: int) -> bool:
        """Mọi candidate đều degraded và priority nằm trong ngưỡng shed của policy."""
        policy = self.policy_store.get(route)
        if not policy or not policy.candidates:
            return False
        inputs = self._candidate_inputs(policy, route)
        all_degraded = all(
            i.breaker_open or not i.eligible or i.health < DEGRADED_HEALTH for i in inputs.values()
        )
        return should_shed(policy.shed, priority, all_degraded)

    def shed(self, ctx: RequestContext) -> OrchestratorResult:
        policy = self.policy_store.get(ctx.route)
        return self._shed_result(ctx, policy.version if policy else 1)

    def _shed_result(self, ctx: RequestContext, policy_ver: int) -> OrchestratorResult:
        req_event = RequestEvent(
            ts=self.clock(),
            meta=RequestMeta(route=ctx.route, env=self.env, synthetic=False),
            request_id=ctx.request_id,
            trace_id=ctx.trace_id,
            session=ctx.session,
            priority=ctx.priority,
            outcome=RequestOutcome.SHED,
            attempts=0,
            latency_ms=0.0,
            policy_version=policy_ver,
        )
        self.telemetry_queue.put_nowait(req_event)
        metrics.emit_request(req_event)
        body = {
            "error": {
                "message": "Route is degraded; low-priority traffic is being shed",
                "type": "service_unavailable",
                "code": "shed",
                "reflex": {"reason": "shed"},
            }
        }
        return OrchestratorResult(
            body=body,
            request_event=req_event,
            attempt_events=[],
            status=503,
            retry_after_s=SHED_RETRY_AFTER_S,
        )

    async def _call(
        self, target_id: str, route: str, payload: dict, timeout_s: float
    ) -> UpstreamResult:
        # route đi kèm target: mock chọn output theo route, chaos-proxy chọn fault theo route
        target = {**self.target_catalog.get(target_id), "route": route}
        adapter = get_adapter(target.get("adapter", "mock"))
        self.state.inflight_start(target_id, route)
        try:
            with llmobs.span(
                "llm",
                f"gateway.attempt.{route}",
                model_name=target_id,
                model_provider=str(target.get("vendor", "unknown")),
            ) as s:
                res = await adapter.complete(target, payload, timeout_s=timeout_s)
                llmobs.annotate(
                    s,
                    input_data=payload.get("messages", []),
                    output_data=[{"role": "assistant", "content": res.content}],
                    metrics={
                        "input_tokens": res.tokens_in,
                        "output_tokens": res.tokens_out,
                        "total_tokens": res.tokens_in + res.tokens_out,
                    },
                    tags={
                        "route": route,
                        "target": target_id,
                        "http_status": res.status,
                        "finish_reason": res.finish_reason or "",
                    },
                )
                return res
        finally:
            self.state.inflight_end(target_id, route)

    async def _call_maybe_hedged(
        self,
        ctx: RequestContext,
        policy: Policy | None,
        ordered_targets: list[str],
        target_id: str,
        payload: dict,
        timeout_s: float,
    ) -> tuple[UpstreamResult, str, bool]:
        """Trả (kết quả, target thực sự trả lời, hedge đã bắn chưa).

        Hedge chỉ cho attempt đầu: chờ p95 của target; nếu chưa xong và còn ngân sách thì bắn
        thêm sang target kế tiếp, bên nào trả 200 trước thắng và bên kia bị hủy.
        """
        primary = asyncio.create_task(self._call(target_id, ctx.route, payload, timeout_s))
        alt = next((t for t in ordered_targets if t != target_id), None)
        delay_ms = None
        if policy is not None and alt is not None:
            delay_ms = hedge_delay_ms(policy.hedge, self.state.latency_p95_ms(target_id, ctx.route))
        if policy is None or alt is None or delay_ms is None or delay_ms / 1000.0 >= timeout_s:
            return await primary, target_id, False

        done, _ = await asyncio.wait({primary}, timeout=delay_ms / 1000.0)
        if done:
            return primary.result(), target_id, False
        if not self._get_hedge_budget(ctx.route, policy).try_acquire():
            return await primary, target_id, False

        hedge = asyncio.create_task(self._call(alt, ctx.route, payload, timeout_s))
        owner = {primary: target_id, hedge: alt}
        pending = {primary, hedge}
        fallback: tuple[UpstreamResult, str] | None = None
        error: BaseException | None = None
        winner: tuple[UpstreamResult, str] | None = None
        while pending and winner is None:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task.exception() is not None:
                    error = task.exception()
                    continue
                res = task.result()
                if res.status == 200:
                    winner = (res, owner[task])
                    break
                if fallback is None or owner[task] == target_id:
                    fallback = (res, owner[task])
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        chosen = winner or fallback
        if chosen is None:
            assert error is not None
            raise error
        return chosen[0], chosen[1], True

    async def complete(self, ctx: RequestContext, payload: dict) -> OrchestratorResult:
        now = self.clock()
        policy = self.policy_store.get(ctx.route)
        policy_ver = policy.version if policy else 1

        if self.should_shed(ctx.route, ctx.priority):
            return self._shed_result(ctx, policy_ver)

        if policy:
            rb = self._get_retry_budget(ctx.route, policy)
            rb.record_request()
            self._get_hedge_budget(ctx.route, policy).record_request()

        # 1. Thu thập inputs cho routing
        deadline = Deadline(ctx.deadline_ms or (policy.deadline_ms if policy else 8000))
        if policy and policy.candidates:
            target_inputs = self._candidate_inputs(policy, ctx.route)
            route_decision = decide(policy, target_inputs, self.rng)
            ordered_targets = route_decision.ordered
        else:
            ordered_targets = ["mock:large"]

        if not ordered_targets:
            ordered_targets = ["mock:large"]

        primary_target_id = ordered_targets[0]
        attempt_events: list[AttemptEvent] = []
        final_response: Any = None
        final_quality: QualityResult | None = None
        final_target_id = primary_target_id
        hedged = False

        val_chain = build_chain(policy.validators if policy else ["not_empty"])
        max_attempts = policy.retry.max_attempts if policy else 2

        # Vòng lặp attempt: Primary → Retry/Rescue
        for att_idx in range(1, max_attempts + 1):
            target_idx = min(att_idx - 1, len(ordered_targets) - 1)
            target_id = ordered_targets[target_idx]
            final_target_id = target_id
            breaker = self._get_breaker(target_id, policy.breaker if policy else BreakerConfig())
            if att_idx == 1:
                att_kind = AttemptKind.PRIMARY
            elif final_quality is not None and not final_quality.pass_:
                att_kind = AttemptKind.QUALITY_RETRY
            else:
                att_kind = AttemptKind.RETRY

            if att_idx > 1 and not deadline.allows(
                self.state.expected_latency_ms(target_id, ctx.route)
            ):
                break

            timeout_s = min(deadline.remaining_ms() / 1000.0, 30.0)
            up_res, answered_by, fired = await self._call_maybe_hedged(
                ctx,
                policy,
                ordered_targets if att_idx == 1 else [],  # hedge chỉ cho attempt đầu
                target_id,
                payload,
                timeout_s,
            )
            hedged = hedged or fired
            if answered_by != target_id:
                target_id = final_target_id = answered_by
                att_kind = AttemptKind.HEDGE
                breaker = self._get_breaker(
                    target_id, policy.breaker if policy else BreakerConfig()
                )
            target = self.target_catalog.get(target_id)

            # Chạy validators
            norm_resp = NormalizedResponse(
                content=up_res.content,
                finish_reason=up_res.finish_reason,
                route=ctx.route,
                tokens_out=up_res.tokens_out,
            )
            checks = run_chain(val_chain, norm_resp)
            failed_checks = [c.name for c in checks if not c.passed]
            passed = len(failed_checks) == 0
            truncated = up_res.finish_reason == "length"

            q_res = QualityResult(
                pass_=passed,
                checks=[c.name for c in checks],
                failed=failed_checks,
                truncated=truncated,
            )
            final_quality = q_res

            # Phân loại failure
            f_class = classify(
                http_status=up_res.status,
                error_class=up_res.error_class,
                quality_failed=not passed,
            )

            # Record breaker outcome
            breaker.record(success=passed and up_res.status == 200, at=now)
            self.state.on_attempt(target_id, ctx.route, ok=up_res.status == 200, quality_ok=passed)
            if up_res.status == 200:
                self.state.record_latency(target_id, ctx.route, up_res.latency_ms)

            if up_res.status == 200:
                att_outcome = AttemptOutcome.OK if passed else AttemptOutcome.QUALITY_FAIL
            elif up_res.status == 504:
                att_outcome = AttemptOutcome.TIMEOUT
            elif up_res.status == 429:
                att_outcome = AttemptOutcome.RATE_LIMITED
            else:
                att_outcome = AttemptOutcome.ERROR

            price = target.get("price", {})
            in_price = float(price.get("in_per_mtok", 0.0)) / 1_000_000.0
            out_price = float(price.get("out_per_mtok", 0.0)) / 1_000_000.0
            cost = (up_res.tokens_in * in_price) + (up_res.tokens_out * out_price)

            att_event = AttemptEvent(
                ts=now,
                meta=AttemptMeta(target=target_id, env=self.env, synthetic=False),
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                route=ctx.route,
                attempt_no=att_idx,
                kind=att_kind,
                outcome=att_outcome,
                http_status=up_res.status,
                error_class=up_res.error_class,
                finish_reason=up_res.finish_reason,
                latency_ms=up_res.latency_ms,
                ttft_ms=up_res.ttft_ms,
                tokens_in=up_res.tokens_in,
                tokens_out=up_res.tokens_out,
                quality=q_res,
                cost_usd=cost,
                gateway_id=self.gateway_id,
                breaker_state=breaker.state.value,
            )
            attempt_events.append(att_event)
            self.telemetry_queue.put_nowait(att_event)
            metrics.emit_attempt(att_event)
            spans.tag_attempt_span(
                spans.current_span(),
                {
                    "route": ctx.route,
                    "target": target_id,
                    "attempt_kind": att_kind.value,
                    "outcome": att_outcome.value,
                    "policy_version": policy_ver,
                    "gateway_id": self.gateway_id,
                },
            )

            final_response = up_res.raw

            # Nếu thành công -> thoát loop
            if att_outcome == AttemptOutcome.OK:
                break

            # Nếu lỗi vĩnh viễn (permanent) -> không retry
            if f_class == FailureClass.PERMANENT:
                break

            # Nếu là quality fail và không cho rescue -> không retry
            if f_class == FailureClass.QUALITY and policy and not policy.rescue.enabled:
                break

            # Tiếp tục retry/rescue nếu còn lượt
            if att_idx < max_attempts:
                await asyncio.sleep(0.01)

        # Tính toán RequestEvent tổng
        last_att = attempt_events[-1]
        req_outcome = (
            RequestOutcome.OK
            if last_att.outcome == AttemptOutcome.OK
            else RequestOutcome.QUALITY_FAIL
        )
        if last_att.outcome in (
            AttemptOutcome.TIMEOUT,
            AttemptOutcome.RATE_LIMITED,
            AttemptOutcome.ERROR,
        ):
            req_outcome = RequestOutcome.ERROR

        total_tokens_in = sum(a.tokens_in for a in attempt_events)
        total_tokens_out = sum(a.tokens_out for a in attempt_events)
        total_cost = sum(a.cost_usd for a in attempt_events)
        total_latency = sum(a.latency_ms for a in attempt_events)

        req_event = RequestEvent(
            ts=now,
            meta=RequestMeta(route=ctx.route, env=self.env, synthetic=False),
            request_id=ctx.request_id,
            trace_id=ctx.trace_id,
            session=ctx.session,
            priority=ctx.priority,
            outcome=req_outcome,
            final_target=final_target_id,
            primary_target=primary_target_id,
            attempts=len(attempt_events),
            hedged=hedged,
            latency_ms=total_latency,
            ttft_ms=attempt_events[0].ttft_ms,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            cost_usd=total_cost,
            quality=final_quality,
            policy_version=policy_ver,
        )
        self.telemetry_queue.put_nowait(req_event)
        metrics.emit_request(req_event)

        # Hết attempt mà lần cuối vẫn lỗi → trả lỗi thật, không 200 + body không có `choices`
        status = 200
        if req_outcome == RequestOutcome.ERROR:
            status = last_att.http_status if (last_att.http_status or 0) >= 400 else 502
        return OrchestratorResult(
            body=final_response or {},
            request_event=req_event,
            attempt_events=attempt_events,
            status=status,
        )

    async def stream(self, ctx: RequestContext, payload: dict) -> AsyncIterator[dict]:
        res = await self.complete(ctx, payload)
        content = res.body.get("choices", [{}])[0].get("message", {}).get("content", "")
        finish_reason = res.attempt_events[-1].finish_reason or "stop"
        yield {
            "choices": [
                {
                    "delta": {"role": "assistant", "content": content},
                    "finish_reason": None,
                }
            ]
        }
        yield {
            "choices": [
                {
                    "delta": {},
                    "finish_reason": finish_reason,
                }
            ]
        }
