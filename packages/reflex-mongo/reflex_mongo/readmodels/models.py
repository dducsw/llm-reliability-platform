"""Read-model Pydantic models cho Console screens (DE-6.1, J-0.6)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PulseReadModel(BaseModel):
    """Read-model cho màn hình Pulse (/): toàn cảnh hệ thống."""

    health: list[dict[str, Any]] = Field(default_factory=list)
    incidents: list[dict[str, Any]] = Field(default_factory=list)
    policies: list[dict[str, Any]] = Field(default_factory=list)


class WarRoomReadModel(BaseModel):
    """Read-model cho màn hình War Room (/incidents/:key): tổng hợp incident, actions, investigation."""

    incident: dict[str, Any]
    actions: list[dict[str, Any]] = Field(default_factory=list)
    investigation: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)
