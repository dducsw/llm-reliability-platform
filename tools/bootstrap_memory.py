"""Script bootstrap 50 incident mẫu vào collection incidents và actions.

Phục vụ giải quyết vấn đề Cold Start cho Incident Memory (P7, DE-7.2),
giúp Cortex Vector Search (A10) ngay lập tức tìm thấy tiền lệ và tỉ lệ thành công của các action.
"""

from __future__ import annotations

import asyncio
import os
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from dotenv import load_dotenv
from reflex_mongo.client import get_db, make_client
from reflex_mongo.collections import ACTIONS, INCIDENTS

load_dotenv()

DEFAULT_DB = "reflex"


def _build_signature(sli: str, cause: str) -> list[float]:
    """Sinh vector 64D chuẩn hóa [c1(16), c2(16), c3(16), c4(16)]."""
    c1 = [0.0] * 16
    c2 = [0.0] * 16
    c3 = [0.0] * 16
    c4 = [0.0] * 16

    # Thêm chút noise ngẫu nhiên để các incident không giống hệt nhau 100%
    def noise(scale: float = 0.05) -> float:
        return random.uniform(-scale, scale)

    if cause == "output_truncation":
        # Cửa sổ sự cố (t-12m đến t+3m): c2 tăng vọt lên ~0.7-0.9
        for i in range(4, 13):
            c2[i] = min(1.0, max(0.0, 0.75 + noise(0.1)))
        c2[13] = 0.4 + noise()
    elif cause == "tail_latency":
        for i in range(4, 13):
            c3[i] = min(1.0, max(-1.0, 0.8 + noise(0.1)))
            c4[i] = min(1.0, max(-1.0, 0.7 + noise(0.1)))
    elif cause == "rate_limit_storm":
        for i in range(4, 13):
            c1[i] = min(1.0, max(0.0, 0.65 + noise(0.1)))
    elif cause == "provider_down":
        for i in range(4, 13):
            c1[i] = min(1.0, max(0.0, 0.95 + noise(0.05)))

    # Gộp 4 vector 16 phần tử thành 64 phần tử
    vec = [round(v, 4) for v in (c1 + c2 + c3 + c4)]
    return vec


async def bootstrap_memory(uri: str, db_name: str = DEFAULT_DB) -> dict[str, int]:
    client = make_client(uri, app_name="reflex-bootstrap-memory")
    db = get_db(client, db_name)
    now = datetime.now(tz=UTC)

    categories = [
        ("output_truncation", "quality", "vendorA:large", ["order.extract"], 20, "shift_weight"),
        ("tail_latency", "latency", "vendorA:large", ["chat.reply"], 10, "hedge"),
        (
            "rate_limit_storm",
            "availability",
            "vendorA:large",
            ["support.triage"],
            10,
            "shed_priority",
        ),
        (
            "provider_down",
            "availability",
            "vendorB:fallback",
            ["order.extract"],
            10,
            "open_circuit_global",
        ),
    ]

    inc_docs: list[dict[str, Any]] = []
    act_docs: list[dict[str, Any]] = []

    inc_idx = 1
    for cause, sli, target, routes, count, best_action in categories:
        for i in range(count):
            inc_key = f"INC-HIST-{inc_idx:03d}"
            detected_at = now - timedelta(days=random.randint(1, 40), hours=random.randint(0, 23))
            first_bad_at = detected_at - timedelta(seconds=random.randint(30, 90))
            resolved_at = detected_at + timedelta(seconds=random.randint(120, 600))

            vec = _build_signature(sli, cause)

            inc_doc = {
                "_id": inc_key,
                "key": inc_key,
                "dedup_key": f"target:{target}:{routes[0]}:{inc_key}",
                "is_open": False,
                "slo_id": f"target:{target}:{sli}",
                "scope": "target",
                "target": target,
                "routes": routes,
                "sli": sli,
                "severity": "critical",
                "status": "resolved",
                "diagnosis": {
                    "side": "provider",
                    "cause_class": cause,
                    "confidence": 0.92,
                    "by": "cortex",
                },
                "signature": {
                    "v": 2,
                    "vec": vec,
                    "window": {
                        "from": (detected_at - timedelta(minutes=12)).isoformat(),
                        "to": (detected_at + timedelta(minutes=4)).isoformat(),
                    },
                },
                "t": {
                    "first_bad_at": first_bad_at,
                    "detected_at": detected_at,
                    "acknowledged_at": detected_at + timedelta(seconds=15),
                    "mitigated_at": detected_at + timedelta(seconds=45),
                    "resolved_at": resolved_at,
                },
                "synthetic": True,
                "created_at": detected_at,
                "updated_at": resolved_at,
            }
            inc_docs.append(inc_doc)

            # Tạo 1 action chính (hầu hết PASS, thỉnh thoảng có FAIL để học kinh nghiệm)
            action_id = f"act-{inc_key}-1"
            is_pass = i % 5 != 0  # 80% PASS, 20% FAIL
            action_type = (
                best_action
                if is_pass
                else ("retry" if best_action != "retry" else "open_circuit_global")
            )

            act_doc = {
                "_id": action_id,
                "incident_id": inc_key,
                "parent_action_id": None,
                "type": action_type,
                "state": "succeeded" if is_pass else "failed",
                "params": {"target": target, "route": routes[0]},
                "ttr_s": random.randint(35, 75) if is_pass else random.randint(180, 400),
                "verification": {
                    "verdict": "PASS" if is_pass else "FAIL",
                    "p_value": 0.001 if is_pass else 0.45,
                },
                "applied_at": detected_at + timedelta(seconds=20),
                "created_at": detected_at + timedelta(seconds=20),
            }
            act_docs.append(act_doc)
            inc_idx += 1

    # Upsert vào DB
    for doc in inc_docs:
        await db[INCIDENTS].update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)

    for doc in act_docs:
        await db[ACTIONS].update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)

    await client.close()
    return {"incidents": len(inc_docs), "actions": len(act_docs)}


def main() -> None:
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?directConnection=true")
    res = asyncio.run(bootstrap_memory(uri))
    print(
        f"Bootstrapped Incident Memory successfully: {res['incidents']} incidents, {res['actions']} actions."
    )


if __name__ == "__main__":
    main()
