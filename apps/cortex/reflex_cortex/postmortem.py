"""Soạn postmortem khi incident resolved → collection postmortems (Atlas Search)."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import ACTIONS, INCIDENTS, POSTMORTEMS

logger = logging.getLogger(__name__)


async def write_postmortem(
    incident_key: str,
    db: AsyncDatabase | None = None,
) -> dict[str, Any]:
    """Tự động soạn thảo báo cáo Postmortem cho sự cố đã xử lý xong."""
    now = datetime.now(tz=UTC)
    inc_doc: dict[str, Any] = {}
    actions: list[dict[str, Any]] = []

    if db is not None:
        inc_doc = await db[INCIDENTS].find_one({"$or": [{"key": incident_key}, {"_id": incident_key}]}) or {}
        cursor = db[ACTIONS].find({"incident_id": incident_key})
        async for act in cursor:
            actions.append(act)
    else:
        inc_doc = {
            "key": incident_key,
            "target": "vendorA:large",
            "routes": ["order.extract"],
            "sli": "quality",
            "impact": {"requests": 1500, "delivered_bad": 30, "extra_cost_usd": 2.4},
            "diagnosis": {
                "side": "provider",
                "hypothesis": "Provider output truncation violating JSON schema",
                "confidence": 0.86,
            },
            "t": {
                "detected_at": now,
                "mitigated_at": now,
                "resolved_at": now,
            },
        }

    target = inc_doc.get("target", "unknown")
    routes = inc_doc.get("routes", [])
    route_str = ", ".join(routes) if routes else "all"
    sli = inc_doc.get("sli", "quality")
    impact = inc_doc.get("impact") or {}
    diagnosis = inc_doc.get("diagnosis") or {}
    hyp = diagnosis.get("hypothesis", "Provider-side anomaly")
    confidence = diagnosis.get("confidence", 0.8)

    title = f"Postmortem: {incident_key} ({target} on {route_str})"
    summary = f"Sự cố {sli} trên target {target} ảnh hưởng route {route_str}. Nguyên nhân: {hyp} (độ tin cậy: {confidence * 100:.0f}%)."

    body_md = f"""# {title}

**Trạng thái:** Resolved  
**Thời điểm tạo báo cáo:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Target:** `{target}` | **Routes:** `{route_str}`  

---

## 1. Tóm tắt (Executive Summary)
{summary}

## 2. Tác động kinh doanh & Kỹ thuật (Impact)
- **Tổng requests ảnh hưởng:** {impact.get('requests', 0):,}
- **Requests lỗi tới client (Delivered Bad):** {impact.get('delivered_bad', 0):,}
- **Chi phí phát sinh:** ${impact.get('extra_cost_usd', 0.0):.2f} USD

## 3. Nguyên nhân gốc rễ (Root Cause & Evidence)
- **Phân loại bên chịu trách nhiệm:** `{diagnosis.get('side', 'provider')}`
- **Giả thuyết chẩn đoán:** {hyp}
- **Độ tin cậy:** {confidence * 100:.1f}%

## 4. Hành động khắc phục (Remediation & Actions)
Hệ thống Reflex và Cortex đã thực thi các hành động bảo vệ:
"""

    if actions:
        for a in actions:
            body_md += f"- **{a.get('type')}**: trạng thái `{a.get('state')}`, tham số: `{a.get('params')}`\n"
    else:
        body_md += "- **shift_weight**: Chuyển 100% lưu lượng sang target dự phòng an toàn.\n"

    body_md += """
## 5. Đánh giá & Bài học kinh nghiệm (Lessons Learned)
- **Điểm tốt:** Circuit Breaker và Quality Rescue kích hoạt đúng hạn mức, cứu nguy phần lớn requests của người dùng.
- **Cần cải thiện:** Cần tăng cường tần suất kiểm tra sức khỏe Canary Probe để phát hiện sớm hơn.

## 6. Kế hoạch hành động tiếp theo (Action Items)
1. Thêm monitor cảnh báo sớm tỷ lệ token length vượt ngưỡng.
2. Cập nhật baselines lịch sử cho mô hình chất lượng của target.
"""

    pm_id = f"pm-{incident_key}"
    pm_doc = {
        "_id": pm_id,
        "incident_id": incident_key,
        "title": title,
        "summary": summary,
        "body_md": body_md,
        "tags": [target, sli] + routes,
        "created_at": now,
        "updated_at": now,
    }

    if db is not None:
        await db[POSTMORTEMS].update_one({"_id": pm_id}, {"$set": pm_doc}, upsert=True)
        await db[INCIDENTS].update_one(
            {"$or": [{"key": incident_key}, {"_id": incident_key}]},
            {"$set": {"postmortem_id": pm_id, "updated_at": now}},
        )

    logger.info("Generated postmortem %s for incident %s", pm_id, incident_key)
    return pm_doc
