from __future__ import annotations

from pydantic import BaseModel, field_validator


class DatadogWebhookPayload(BaseModel):
    """Body do template webhook trong infra/terraform/webhooks.tf định nghĩa."""

    monitor_id: int
    alert_id: str | None = None
    alert_transition: str
    title: str
    tags: list[str] = []
    diagnosis: str | None = None
    date: int | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _split_tags(cls, v: object) -> object:
        # Datadog render $TAGS thành một chuỗi "a:b,c:d", không phải mảng JSON.
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v
