"""Schema scenario YAML (incident-scenarios.md §3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Traffic(BaseModel):
    rps: float
    mix: dict[str, float]
    diurnal: dict[str, Any] | None = None


class PhaseFault(BaseModel):
    target: str
    route: str | None = None
    type: str
    params: dict[str, Any] = {}


class Phase(BaseModel):
    at: str
    duration: str
    faults: list[PhaseFault] = []


class Scenario(BaseModel):
    name: str
    profile: str = "demo"
    seed: int = 42
    traffic: Traffic
    phases: list[Phase]
    expectations: list[dict[str, Any]] = []
    ground_truth: dict[str, str] | None = None  # KHÔNG bao giờ đưa vào Cortex
