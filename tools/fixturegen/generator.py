"""Core generation logic for attempts, requests, probes with fault injection (DE-0.3)."""

from __future__ import annotations

import random
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class FixtureConfig:
    total_requests: int = 10_000
    start_time: datetime = field(default_factory=lambda: datetime.now(tz=UTC) - timedelta(hours=2))
    rps: float = 10.0
    seed: int = 42
    env: str = "local"
    primary_target: str = "vendorA:large"
    fallback_target: str = "vendorB:fallback"
    routes: list[str] = field(
        default_factory=lambda: ["chat.reply", "order.extract", "catalog.search"]
    )
    inject_fault: bool = True
    fault_type: str = "quality_fail"  # quality_fail, rate_limited, timeout, 500
    fault_target: str = "vendorA:large"
    fault_window_start_sec: float = 600.0  # T+10m
    fault_window_duration_sec: float = 1800.0  # 30m fault
    fault_rate: float = 0.40  # 40% failure in fault window


def generate_fixtures(
    cfg: FixtureConfig,
) -> Iterator[tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]]:
    """Yields (request_doc, attempt_docs, optional_probe_doc) for each request cycle.

    Deterministic using seeded Random.
    """
    rng = random.Random(cfg.seed)
    current_time = cfg.start_time
    dt_per_req = timedelta(seconds=1.0 / max(0.1, cfg.rps))

    probe_interval = timedelta(seconds=15)
    last_probe_time = current_time - probe_interval

    for i in range(cfg.total_requests):
        current_time += dt_per_req
        req_id = f"req-{cfg.seed}-{i:07d}"
        trace_id = uuid.UUID(int=rng.getrandbits(128)).hex
        route = rng.choice(cfg.routes)
        session = f"sess_{rng.randint(1, 200)}"
        priority = rng.choices([0, 1, 2], weights=[0.2, 0.7, 0.1])[0]

        elapsed_sec = (current_time - cfg.start_time).total_seconds()
        in_fault_window = cfg.inject_fault and cfg.fault_window_start_sec <= elapsed_sec <= (
            cfg.fault_window_start_sec + cfg.fault_window_duration_sec
        )

        attempts: list[dict[str, Any]] = []

        # Attempt 1 (primary target)
        target = cfg.primary_target
        is_target_faulty = (
            in_fault_window and (target == cfg.fault_target) and (rng.random() < cfg.fault_rate)
        )

        att1_latency = rng.gauss(250.0, 30.0)
        att1_ttft = rng.gauss(90.0, 15.0)

        if is_target_faulty:
            if cfg.fault_type == "quality_fail":
                outcome = "quality_fail"
                quality = {
                    "pass": False,
                    "checks": ["json_schema", "not_empty"],
                    "failed": ["json_schema"],
                    "truncated": True,
                }
                http_status = 200
            elif cfg.fault_type == "rate_limited":
                outcome = "rate_limited"
                quality = None
                http_status = 429
            elif cfg.fault_type == "timeout":
                outcome = "timeout"
                quality = None
                http_status = 504
                att1_latency = 5000.0
            else:
                outcome = "error"
                quality = None
                http_status = 500
        else:
            outcome = "ok"
            quality = {
                "pass": True,
                "checks": ["json_schema", "not_empty"],
                "failed": [],
                "truncated": False,
            }
            http_status = 200

        attempts.append(
            {
                "ts": current_time,
                "meta": {"target": target, "env": cfg.env, "synthetic": False},
                "v": 1,
                "request_id": req_id,
                "trace_id": trace_id,
                "span_id": uuid.UUID(int=rng.getrandbits(128)).hex[:16],
                "route": route,
                "attempt_no": 1,
                "kind": "primary",
                "outcome": outcome,
                "http_status": http_status,
                "error_class": None if outcome == "ok" else outcome,
                "finish_reason": "stop" if outcome == "ok" else "error",
                "latency_ms": round(max(10.0, att1_latency), 2),
                "ttft_ms": round(max(5.0, att1_ttft), 2),
                "tps": round(rng.uniform(25.0, 45.0), 1),
                "tokens_in": rng.randint(150, 400),
                "tokens_out": rng.randint(50, 350) if outcome == "ok" else 20,
                "quality": quality,
                "cost_usd": 0.002,
                "gateway_id": "gw-1",
                "breaker_state": "closed",
            }
        )

        # Reflex rescue attempt if attempt 1 failed
        final_target = target
        req_outcome = "ok"
        total_attempts = 1
        hedged = False
        retry_reasons = []

        if outcome != "ok":
            retry_reasons.append(outcome)
            # Failover to secondary target
            target2 = cfg.fallback_target
            att2_time = current_time + timedelta(milliseconds=att1_latency)
            att2_latency = rng.gauss(280.0, 35.0)
            att2_ttft = rng.gauss(95.0, 15.0)

            attempts.append(
                {
                    "ts": att2_time,
                    "meta": {"target": target2, "env": cfg.env, "synthetic": False},
                    "v": 1,
                    "request_id": req_id,
                    "trace_id": trace_id,
                    "span_id": uuid.UUID(int=rng.getrandbits(128)).hex[:16],
                    "route": route,
                    "attempt_no": 2,
                    "kind": "rescue" if outcome == "quality_fail" else "retry",
                    "outcome": "ok",
                    "http_status": 200,
                    "error_class": None,
                    "finish_reason": "stop",
                    "latency_ms": round(max(10.0, att2_latency), 2),
                    "ttft_ms": round(max(5.0, att2_ttft), 2),
                    "tps": round(rng.uniform(22.0, 40.0), 1),
                    "tokens_in": attempts[0]["tokens_in"],
                    "tokens_out": rng.randint(80, 300),
                    "quality": {
                        "pass": True,
                        "checks": ["json_schema", "not_empty"],
                        "failed": [],
                        "truncated": False,
                    },
                    "cost_usd": 0.0025,
                    "gateway_id": "gw-1",
                    "breaker_state": "closed",
                }
            )
            total_attempts = 2
            final_target = target2
            req_outcome = "ok"  # Cứu sống thành công (Delivered = 99%+)

        total_lat = sum(a["latency_ms"] for a in attempts)
        total_tokens_in = sum(a["tokens_in"] for a in attempts)
        total_tokens_out = sum(a["tokens_out"] for a in attempts)
        total_cost = sum(a["cost_usd"] for a in attempts)

        request_doc = {
            "ts": current_time,
            "meta": {"route": route, "env": cfg.env, "synthetic": False},
            "v": 1,
            "request_id": req_id,
            "trace_id": trace_id,
            "session": session,
            "priority": priority,
            "outcome": req_outcome,
            "final_target": final_target,
            "primary_target": cfg.primary_target,
            "attempts": total_attempts,
            "hedged": hedged,
            "retry_reasons": retry_reasons,
            "latency_ms": round(total_lat, 2),
            "ttft_ms": attempts[0]["ttft_ms"],
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "cost_usd": round(total_cost, 4),
            "quality": attempts[-1]["quality"],
            "policy_version": 1,
            "incident_id": None,
        }

        # Canary probe every 15s
        probe_doc = None
        if (current_time - last_probe_time) >= probe_interval:
            last_probe_time = current_time
            probe_outcome = "quality_fail" if (in_fault_window and rng.random() < 0.3) else "ok"
            probe_doc = {
                "ts": current_time,
                "meta": {"target": cfg.primary_target, "path": "direct", "env": cfg.env},
                "v": 1,
                "golden_id": "golden_ping",
                "outcome": probe_outcome,
                "latency_ms": round(rng.gauss(240.0, 20.0), 2),
                "ttft_ms": 85.0,
                "quality": {
                    "pass": probe_outcome == "ok",
                    "checks": ["not_empty"],
                    "failed": [] if probe_outcome == "ok" else ["not_empty"],
                    "truncated": False,
                },
                "http_status": 200,
            }

        yield request_doc, attempts, probe_doc
