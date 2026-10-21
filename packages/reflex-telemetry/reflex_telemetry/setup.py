"""init(service): ddtrace patch, LLMObs (nếu bật), structlog JSON có trace correlation, DogStatsD.

Unified service tagging: env/service/version lấy từ REFLEX_ENV, tên service, file VERSION.
"""

from __future__ import annotations

from dataclasses import dataclass

from datadog.dogstatsd import DogStatsd


@dataclass(frozen=True, slots=True)
class Telemetry:
    service: str
    env: str
    version: str
    statsd: DogStatsd


def init(service: str, *, llmobs: bool = False) -> Telemetry:
    raise NotImplementedError


def get_logger(name: str):  # type: ignore[no-untyped-def]
    raise NotImplementedError
