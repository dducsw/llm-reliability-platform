"""Sinh output đúng theo route (JSON order_v2 hợp lệ, câu tiếng Việt, triage_v1)."""

from __future__ import annotations

import json
import random

SAMPLE_ORDERS = [
    {
        "items": [{"name": "Trà sữa trân châu", "qty": 2, "variant": "Size L, 50% đường"}],
        "address": "456 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP.HCM",
        "note": "Giao trước 12h",
    },
    {
        "items": [
            {"name": "Cà phê sữa đá", "qty": 1, "variant": "Ít ngọt"},
            {"name": "Bánh mì pate trứng", "qty": 1},
        ],
        "address": "789 Cách Mạng Tháng Tám, Quận 3, TP.HCM",
        "note": "Xin thêm khăn giấy",
    },
]

SAMPLE_CHAT = [
    "Dạ ShopMate xin chào quý khách! Em có thể giúp gì cho đơn hàng của mình ạ?",
    "Cảm ơn quý khách đã liên hệ, ShopMate đang kiểm tra trạng thái đơn hàng giúp mình ạ.",
    "Dạ vâng, đơn hàng của bạn đã được xuất kho và đang trên đường giao tới bạn nhé!",
]


def generate(route: str, messages: list[dict], rng: random.Random) -> str:
    if route == "order.extract":
        return json.dumps(rng.choice(SAMPLE_ORDERS), ensure_ascii=False)
    elif route == "support.triage":
        return json.dumps({"category": "shipping", "urgency": "medium", "sentiment": "neutral"})
    elif route == "cortex.reason":
        return json.dumps(
            {
                "hypothesis": "provider_down",
                "confidence": 0.95,
                "proposed_action": {
                    "type": "shift_weight",
                    "from": "vendorA:large",
                    "to": "vendorB:large",
                    "pct": 90,
                },
            }
        )
    else:
        return rng.choice(SAMPLE_CHAT)
