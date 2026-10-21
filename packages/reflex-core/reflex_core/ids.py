"""ID helpers cho target/route/slo/incident và chuẩn hóa tag.

- target id: "<vendor>:<tier>", vd "vendorA:large"
- slo id:    "<scope>:<key>:<sli>", vd "route:order.extract:quality"
- incident key: "INC-YYYYMMDD-NNNN"
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
import hashlib
import re
from typing import Protocol
import uuid

Clock = Callable[[], datetime]
"""Trả về thời điểm hiện tại (UTC). Inject để test/replay deterministic."""


class Rng(Protocol):
    def random(self) -> float: ...
    def uniform(self, a: float, b: float) -> float: ...


class Route(StrEnum):
    ORDER_EXTRACT = "order.extract"
    CHAT_REPLY = "chat.reply"
    SUPPORT_TRIAGE = "support.triage"
    CORTEX_REASON = "cortex.reason"


class Scope(StrEnum):
    TARGET = "target"
    ROUTE = "route"
    TARGET_ROUTE = "target_route"
    PROBE = "probe"


class SliKind(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    TTFT = "ttft"
    QUALITY = "quality"


def target_id(vendor: str, tier: str) -> str:
    return f"{vendor}:{tier}"


def parse_target_id(target: str) -> tuple[str, str]:
    parts = target.split(":", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")


def slo_id(scope: Scope, key: str, sli: SliKind) -> str:
    return f"{scope}:{key}:{sli}"


def incident_key(at: datetime, seq: int) -> str:
    return f"INC-{at.strftime('%Y%m%d')}-{seq:04d}"


def dedup_key(slo: str, target: str | None, route: str | None) -> str:
    """sha1(slo_id|target|route) — dùng cho partial unique index trên incidents."""
    raw = f"{slo}|{target or '*'}|{route or '*'}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def normalize_tag(value: str) -> str:
    """Chuẩn hóa giá trị tag theo quy tắc Datadog (lowercase, ký tự hợp lệ)."""
    val = value.lower()
    return re.sub(r"[^a-z0-9_.:/-]", "_", val)
