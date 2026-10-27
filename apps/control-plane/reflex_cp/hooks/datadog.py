"""POST /hooks/datadog — kiểm tra X-Reflex-Webhook-Token, map monitor → signal → incident."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from reflex_core.incident import Severity

from reflex_cp.hooks.payload import DatadogWebhookPayload
from reflex_cp.incidents.service import IncidentService

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_tags(tags: list[str]) -> dict[str, str]:
    res = {}
    for t in tags:
        if ":" in t:
            k, v = t.split(":", 1)
            res[k.strip()] = v.strip()
    return res


@router.post("/hooks/datadog")
async def datadog_webhook(
    request: Request,
    payload: DatadogWebhookPayload,
    x_reflex_webhook_token: str | None = Header(default=None, alias="X-Reflex-Webhook-Token"),
) -> dict[str, Any]:
    # Lấy settings từ app.state nếu có
    settings = getattr(request.app.state, "settings", None)
    expected_token = getattr(settings, "reflex_webhook_token", "") if settings else ""
    if expected_token and x_reflex_webhook_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    db = getattr(request.app.state, "db", None)
    incident_service: IncidentService = getattr(
        request.app.state, "incident_service", IncidentService(db)
    )

    tag_map = _parse_tags(payload.tags)
    target = tag_map.get("target")
    route = tag_map.get("route")
    sli = tag_map.get("sli", "quality")
    slo_id = tag_map.get("slo") or tag_map.get("slo_id") or f"dd:{payload.monitor_id}"

    now = datetime.now(tz=UTC)
    signal = {
        "source": "datadog",
        "at": now,
        "monitor_id": payload.monitor_id,
        "alert_id": payload.alert_id,
        "diagnosis": payload.diagnosis,
    }

    # Datadog transition: "Triggered", "Warn", "Alert", "Recovered", etc.
    transition = (payload.alert_transition or "").lower()
    if "recovered" in transition:
        # Đóng incident là việc của Verifier (Recovery Proof), không dựa vào monitor hồi phục.
        return {"ok": True, "incident_key": None, "transition": payload.alert_transition}
    severity = Severity.CRITICAL if "warn" not in transition else Severity.WARNING

    inc = await incident_service.open_or_merge(
        signal=signal,
        slo_id=slo_id,
        target=target,
        route=route,
        severity=severity,
        sli=sli,
    )

    return {
        "ok": True,
        "incident_key": inc.get("key"),
        "transition": payload.alert_transition,
    }
