"""Fault catalog (simulation-and-chaos.md §2)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class FaultType(StrEnum):
    ERROR = "error"
    RATE_LIMIT = "rate_limit"
    LATENCY = "latency"
    TTFT_SHIFT = "ttft_shift"
    TRUNCATE = "truncate"
    CORRUPT_JSON = "corrupt_json"
    EMPTY = "empty"
    REFUSAL = "refusal"
    STALL = "stall"
    CAPACITY = "capacity"
    REPLAY_SHAPE = "replay_shape"


class FaultSelector(BaseModel):
    target: str
    route: str | None = None
    pct_of_traffic: float | None = None


class Fault(BaseModel):
    type: FaultType
    selector: FaultSelector
    params: dict[str, Any] = {}
