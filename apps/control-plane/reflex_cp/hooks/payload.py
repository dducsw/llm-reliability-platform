from __future__ import annotations

from pydantic import BaseModel


class DatadogWebhookPayload(BaseModel):
    """Body do template webhook trong infra/terraform/webhooks.tf định nghĩa."""

    monitor_id: int
    alert_id: str | None = None
    alert_transition: str
    title: str
    tags: list[str] = []
    diagnosis: str | None = None
    date: int | None = None
