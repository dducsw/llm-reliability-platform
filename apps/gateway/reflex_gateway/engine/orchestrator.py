"""Attempt loop: router.decide → adapter.call → validators → retry/rescue/hedge → events."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
import random
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
from reflex_core.ids import Clock, Rng
from reflex_core.policy import BreakerConfig, Policy
from reflex_core.retry import FailureClass, RetryBudget, classify
from reflex_core.routing import RouteDecision, TargetInputs, decide
from reflex_core.validators.base import NormalizedResponse
from reflex_core.validators.registry import build_chain, run_chain
from reflex_gateway.adapters.registry import get_adapter
from reflex_gateway.policy_store import PolicyStore
from reflex_gateway.target_catalog import TargetCatalog
from reflex_gateway.telemetry.queue import TelemetryQueue


@dataclass(slots=True)
class RequestContext:
    request_id: str
    route: str
    priority: int
    session: str | None
    deadline_ms: int
    trace_id: str | None = None


@dataclass(slots=True)
class OrchestratorResult:
    body: dict
    request_event: RequestEvent
    attempt_events: list[AttemptEvent]


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
        self._breakers: dict[str, CircuitBreaker] = {}
        self._retry_budgets: dict[str, RetryBudget] = {}

    def _get_breaker(self, target_id: str, config: BreakerConfig) -> CircuitBreaker:
        if target_id not in self._breakers:
            self._breakers[target_id] = CircuitBreaker(config, clock=self.clock)
        return self._breakers[target_id]

    def _get_retry_budget(self, route: str, policy: Policy) -> RetryBudget:
        if route not in self._retry_budgets:
            self._retry_budgets[route] = RetryBudget(policy.retry, clock=self.clock)
        return self._retry_budgets[route]

    async def complete(self, ctx: RequestContext, payload: dict) -> OrchestratorResult:
        now = self.clock()
        policy = self.policy_store.get(ctx.route)
        policy_ver = policy.version if policy else 1

        if policy:
            rb = self._get_retry_budget(ctx.route, policy)
            rb.record_request()

        # 1. Thu thập inputs cho routing
        target_inputs: dict[str, TargetInputs] = {}
        if policy and policy.candidates:
            for cand in policy.candidates:
                t_info = self.target_catalog.get(cand.target)
                breaker = self._get_breaker(cand.target, policy.breaker)
                is_open = breaker.state == BreakerState.OPEN
                target_inputs[cand.target] = TargetInputs(
                    target=cand.target,
                    health=1.0 if not is_open else 0.0,
                    budget_headroom=1.0,
                    quality=1.0,
                    cost=0.5,
                    capacity=1.0,
                    breaker_open=is_open,
                    eligible=t_info.get("enabled", True),
                )
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

        val_chain = build_chain(policy.validators if policy else ["not_empty"])
        max_attempts = policy.retry.max_attempts if policy else 2

        # Vòng lặp attempt: Primary → Retry/Rescue
        for att_idx in range(1, max_attempts + 1):
            target_idx = min(att_idx - 1, len(ordered_targets) - 1)
            target_id = ordered_targets[target_idx]
            final_target_id = target_id
            target = self.target_catalog.get(target_id)
            adapter = get_adapter(target.get("adapter", "mock"))

            breaker = self._get_breaker(target_id, policy.breaker if policy else BreakerConfig())
            att_kind = AttemptKind.PRIMARY if att_idx == 1 else AttemptKind.RESCUE

            timeout_s = min(float(ctx.deadline_ms) / 1000.0, 30.0)
            up_res = await adapter.complete(target, payload, timeout_s=timeout_s)

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
            RequestOutcome.OK if last_att.outcome == AttemptOutcome.OK else RequestOutcome.QUALITY_FAIL
        )
        if last_att.outcome in (AttemptOutcome.TIMEOUT, AttemptOutcome.RATE_LIMITED, AttemptOutcome.ERROR):
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
            latency_ms=total_latency,
            ttft_ms=attempt_events[0].ttft_ms,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            cost_usd=total_cost,
            quality=final_quality,
            policy_version=policy_ver,
        )
        self.telemetry_queue.put_nowait(req_event)

        return OrchestratorResult(
            body=final_response or {},
            request_event=req_event,
            attempt_events=attempt_events,
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
