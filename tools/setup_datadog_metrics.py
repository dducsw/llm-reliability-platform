"""Thiết lập cấu hình phân phối percentile cho Datadog metrics (idempotent)."""

from __future__ import annotations

import logging
import os

import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("datadog_metrics")


METRICS_WITH_PERCENTILES = [
    {
        "id": "reflex.request.latency",
        "tags": ["env", "route", "outcome"],
    },
    {
        "id": "reflex.attempt.latency",
        "tags": ["env", "route", "target", "outcome"],
    },
    {
        "id": "reflex.attempt.ttft",
        "tags": ["env", "route", "target"],
    },
    {
        "id": "reflex.cortex.investigation.duration",
        "tags": ["env", "status"],
    },
]


def setup_metric_percentiles() -> None:
    load_dotenv()
    api_key = os.environ.get("DD_API_KEY")
    app_key = os.environ.get("DD_APP_KEY")
    site = os.environ.get("DD_SITE", "ap1.datadoghq.com")

    if not api_key or not app_key:
        logger.warning("DD_API_KEY hoặc DD_APP_KEY không tồn tại; bỏ qua thiết lập metrics.")
        return

    headers = {
        "DD-API-KEY": api_key,
        "DD-APPLICATION-KEY": app_key,
        "Content-Type": "application/json",
    }

    for item in METRICS_WITH_PERCENTILES:
        metric_id = item["id"]
        tags = item["tags"]
        payload = {
            "data": {
                "type": "manage_tags",
                "id": metric_id,
                "attributes": {
                    "tags": tags,
                    "metric_type": "distribution",
                    "include_percentiles": True,
                },
            }
        }
        url = f"https://api.{site}/api/v2/metrics/{metric_id}/tags"
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 409:
            # Đã tồn tại, dùng PATCH để cập nhật
            resp = requests.patch(url, headers=headers, json=payload, timeout=15)

        if resp.status_code in (200, 201):
            logger.info("Đã bật percentiles thành công cho %s", metric_id)
        else:
            logger.warning(
                "Không thể bật percentiles cho %s: %s %s", metric_id, resp.status_code, resp.text
            )


if __name__ == "__main__":
    setup_metric_percentiles()
