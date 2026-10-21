"""SLI good/valid, burn rate, error budget math. Thuần, không I/O."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BurnAlert:
    tier: str  # page | ticket | notice
    long: str
    short: str
    factor: float


def ratio(good: int, valid: int) -> float:
    raise NotImplementedError


def burn_rate(good: int, valid: int, objective: float) -> float:
    """burn = (1 - good/valid) / (1 - objective)."""
    raise NotImplementedError


def budget_remaining(good: int, valid: int, objective: float) -> float:
    raise NotImplementedError


def multiwindow_fires(burn_long: float, burn_short: float, factor: float) -> bool:
    raise NotImplementedError


def parse_window(window: str) -> int:
    """'5m' | '1h' | '30s' | '3d' → seconds."""
    raise NotImplementedError
