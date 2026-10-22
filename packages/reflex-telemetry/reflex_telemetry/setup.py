"""init(service): ddtrace patch, LLMObs (nếu bật), structlog JSON có trace correlation, DogStatsD.

Unified service tagging: env/service/version lấy từ REFLEX_ENV, tên service, file VERSION.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import structlog
from datadog.dogstatsd import DogStatsd


@dataclass(frozen=True, slots=True)
class Telemetry:
    service: str
    env: str
    version: str
    statsd: DogStatsd


def _read_version() -> str:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "VERSION"
        if candidate.is_file():
            return candidate.read_text().strip()
    return os.getenv("DD_VERSION", "0.0.0")


def init(service: str, *, llmobs: bool = False) -> Telemetry:
    env = os.getenv("REFLEX_ENV", "local")
    version = _read_version()
    os.environ.setdefault("DD_SERVICE", service)
    os.environ.setdefault("DD_ENV", env)
    os.environ.setdefault("DD_VERSION", version)
    os.environ.setdefault("DD_LOGS_INJECTION", "true")

    if os.getenv("DD_TRACE_ENABLED", "true").lower() != "false":
        from ddtrace import patch

        # Không patch pymongo: integration của ddtrace chưa tương thích AsyncMongoClient (pymongo ≥ 4.9).
        patch(fastapi=True, httpx=True, logging=True)
        if llmobs and os.getenv("DD_API_KEY"):
            from ddtrace.llmobs import LLMObs

            LLMObs.enable(ml_app=service, agentless_enabled=False)

    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_dd_context(service, env, version),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    statsd = DogStatsd(
        host=os.getenv("DD_AGENT_HOST", "localhost"),
        port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")),
        constant_tags=[f"env:{env}", f"service:{service}", f"version:{version}"],
    )
    return Telemetry(service=service, env=env, version=version, statsd=statsd)


def _add_dd_context(service: str, env: str, version: str):  # type: ignore[no-untyped-def]
    def processor(_logger, _name, event_dict):  # type: ignore[no-untyped-def]
        event_dict.setdefault("service", service)
        event_dict.setdefault("env", env)
        event_dict.setdefault("version", version)
        try:
            from ddtrace import tracer

            span = tracer.current_span()
            if span is not None:
                event_dict["dd.trace_id"] = str(span.trace_id)
                event_dict["dd.span_id"] = str(span.span_id)
        except Exception:
            pass
        return event_dict

    return processor


def get_logger(name: str):  # type: ignore[no-untyped-def]
    return structlog.get_logger(name)
