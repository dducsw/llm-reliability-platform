"""Lưu incident đã resolved vào Incident Memory (signature + root cause + action hiệu quả)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import INCIDENTS, SLI_1M
from reflex_mongo.pipelines import a09_signature

logger = logging.getLogger(__name__)


def _generate_synthetic_vector(sli: str, diagnosis: dict[str, Any] | None = None) -> list[float]:
    """Tạo vector 64D giả lập theo đặc trưng sự cố khi sli_1m chưa có đủ dữ liệu."""
    # 4 kênh x 16 phút: c1 (availability), c2 (quality), c3 (latency shift), c4 (ttft shift)
    c1 = [0.0] * 16
    c2 = [0.0] * 16
    c3 = [0.0] * 16
    c4 = [0.0] * 16

    diag_text = str(diagnosis or {}).lower()
    if sli == "quality" or "truncat" in diag_text or "quality" in diag_text:
        # Quality bad ratio cao trong cửa sổ sự cố (t-12 đến t+3)
        c2 = [0.05] * 4 + [0.75] * 8 + [0.10] * 4
    elif sli == "latency" or "tail" in diag_text or "latency" in diag_text:
        c3 = [0.0] * 4 + [0.85] * 8 + [0.2] * 4
        c4 = [0.0] * 4 + [0.70] * 8 + [0.1] * 4
    elif "429" in diag_text or "rate" in diag_text:
        c1 = [0.0] * 4 + [0.60] * 8 + [0.0] * 4
    else:
        # Provider down
        c1 = [0.0] * 4 + [0.95] * 8 + [0.0] * 4

    return c1 + c2 + c3 + c4


async def remember(incident_key: str, db: AsyncDatabase | None = None) -> dict[str, Any] | None:
    """Lưu trữ incident đã hoàn tất giải quyết vào Incident Memory.

    1. Trích xuất signature vector 64 chiều từ dữ liệu SLI thực tế (A9).
    2. Cập nhật incident với trạng thái resolved, gắn signature và đóng incident (is_open=False).
    3. Phục vụ cho truy vấn tìm kiếm sự cố tương đồng $vectorSearch (A10) cho các sự cố trong tương lai.
    """
    now = datetime.now(tz=UTC)
    if db is None:
        logger.warning("remember() gọi với db=None, bỏ qua cập nhật DB")
        return None

    inc = await db[INCIDENTS].find_one({"key": incident_key})
    if not inc:
        inc = await db[INCIDENTS].find_one({"_id": incident_key})
    if not inc:
        logger.error("Incident %s không tìm thấy để lưu vào memory", incident_key)
        return None

    scope = inc.get("scope", "target")
    key = inc.get("target") or (inc.get("routes", [None])[0] if inc.get("routes") else "unknown")
    sli = inc.get("sli", "quality")
    t_info = inc.get("t", {})
    detected_at = t_info.get("detected_at")
    if isinstance(detected_at, str):
        detected_at = datetime.fromisoformat(detected_at)
    elif not isinstance(detected_at, datetime):
        detected_at = now

    # 1. Chạy A9 signature vector
    vec: list[float] | None = None
    try:
        pipeline = a09_signature.build(
            scope="target" if scope.startswith("target") else "route",
            key=key,
            detected_at=detected_at,
        )
        cursor = await (await db[SLI_1M].aggregate(pipeline)).to_list(1)
        if cursor and "vec" in cursor[0] and len(cursor[0]["vec"]) == 64:
            vec = [float(v) for v in cursor[0]["vec"]]
    except Exception as exc:
        logger.warning("Không thể tính vector A9 từ sli_1m: %s", exc)

    if vec is None:
        vec = _generate_synthetic_vector(sli, inc.get("diagnosis"))

    window = {
        "from": (detected_at - timedelta(minutes=12)).isoformat(),
        "to": (detected_at + timedelta(minutes=4)).isoformat(),
    }

    update_fields = {
        "signature": {
            "v": 2,
            "vec": vec,
            "window": window,
        },
        "status": "resolved",
        "is_open": False,
        "t.resolved_at": now,
        "updated_at": now,
    }

    await db[INCIDENTS].update_one({"_id": inc["_id"]}, {"$set": update_fields})
    logger.info("Saved incident %s into memory with 64D signature vector", incident_key)

    inc.update(update_fields)
    return inc
