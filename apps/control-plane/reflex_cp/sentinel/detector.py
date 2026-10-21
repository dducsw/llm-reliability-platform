"""Multi-window rule → mở incident (source: sentinel). A6 anomaly, A7 probe blindness."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from reflex_core.incident import Severity
from reflex_cp.incidents.service import IncidentService

logger = logging.getLogger(__name__)


class Detector:
    def __init__(self, incident_service: IncidentService | None = None) -> None:
        self.incident_service = incident_service

    async def detect(self, evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Duyệt các đánh giá SLO; nếu vi phạm đa cửa sổ (fires == True) thì mở/gộp incident."""
        if not evaluations or self.incident_service is None:
            return []

        now = datetime.now(tz=UTC)
        incidents: list[dict[str, Any]] = []

        for ev in evaluations:
            if not ev.get("fires"):
                continue

            slo_id = ev.get("slo_id", "unknown_slo")
            target = ev.get("target")
            route = ev.get("route")
            sli = ev.get("sli", "quality")
            burn_short = float(ev.get("burn_short", 0.0))
            burn_long = float(ev.get("burn_long", 0.0))

            severity = Severity.CRITICAL if burn_short >= 30.0 else Severity.WARNING

            signal = {
                "source": "sentinel",
                "at": now,
                "burn": {
                    "short": burn_short,
                    "long": burn_long,
                },
            }

            try:
                inc = await self.incident_service.open_or_merge(
                    signal=signal,
                    slo_id=slo_id,
                    target=target,
                    route=route,
                    severity=severity,
                    sli=sli,
                )
                incidents.append(inc)
            except Exception as e:
                logger.error("Error opening incident for %s: %s", slo_id, e)

        return incidents
