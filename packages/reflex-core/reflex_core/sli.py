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
    """Tỉ lệ good/valid. Khi valid == 0, mặc định 1.0 (không có lỗi)."""
    if valid <= 0:
        return 1.0
    return good / valid


def burn_rate(good: int, valid: int, objective: float) -> float:
    """burn = (1 - good/valid) / (1 - objective)."""
    if valid <= 0:
        return 0.0
    error_budget = 1.0 - objective
    if error_budget <= 0.0:
        return 0.0
    error_rate = 1.0 - (good / valid)
    return error_rate / error_budget


def budget_remaining(good: int, valid: int, objective: float) -> float:
    """Tỉ lệ error budget còn lại: 1.0 - burn_rate."""
    if valid <= 0:
        return 1.0
    error_budget = 1.0 - objective
    if error_budget <= 0.0:
        return 0.0
    error_rate = 1.0 - (good / valid)
    return 1.0 - (error_rate / error_budget)


def multiwindow_fires(burn_long: float, burn_short: float, factor: float) -> bool:
    """Cả hai cửa sổ dài và ngắn đều phải vượt ngưỡng factor."""
    return burn_long >= factor and burn_short >= factor


def parse_window(window: str) -> int:
    """'5m' | '1h' | '30s' | '3d' → seconds."""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    w = window.strip().lower()
    if not w:
        return 0
    unit = w[-1]
    if unit in units:
        return int(w[:-1]) * units[unit]
    return int(w)
