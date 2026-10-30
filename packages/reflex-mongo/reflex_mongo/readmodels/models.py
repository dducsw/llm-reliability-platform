"""Read-model Pydantic models cho Console screens (DE-6.1, J-0.6)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PulseKpis(BaseModel):
    """KPI dải đầu màn hình Pulse: chất lượng/khả dụng 60m, MTTX 7 ngày, chi phí hôm nay."""

    quality: float | None = None
    availability: float | None = None
    mttd_p50_s: float | None = None
    mttr_p50_s: float | None = None
    cost_usd_today: float = 0.0
    tokens_in_today: int = 0
    tokens_out_today: int = 0
    requests_today: int = 0


class PulseReadModel(BaseModel):
    """Read-model cho màn hình Pulse (/): toàn cảnh hệ thống."""

    health: list[dict[str, Any]] = Field(default_factory=list)
    incidents: list[dict[str, Any]] = Field(default_factory=list)
    policies: list[dict[str, Any]] = Field(default_factory=list)
    kpis: PulseKpis | None = None


class WarRoomReadModel(BaseModel):
    """Read-model cho màn hình War Room (/incidents/:key): tổng hợp incident, actions, investigation."""

    incident: dict[str, Any]
    actions: list[dict[str, Any]] = Field(default_factory=list)
    investigation: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    postmortem: dict[str, Any] | None = None
