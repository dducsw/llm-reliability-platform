"""Prompt synthetic tiếng Việt từ template + từ điển sản phẩm hư cấu (không PII)."""

from __future__ import annotations

import random

_ORDER_PROMPTS = [
    "Cho mình 2 trà sữa ô long nướng trân châu đen size L ít đá giao qua 45 Lê Duẩn, Phường Bến Nghé, Quận 1",
    "Giao 1 phần cơm gà xối mỡ và 1 canh rong biển đến số 12 đường Trần Hưng Đạo, Quận 5",
    "Đặt 3 ly cà phê đen đá và 1 bánh sừng bò về tầng 8 toà nhà Bitexco, Q1",
    "Ship gấp 2 hộp pizza hải sản cỡ vừa và 1 chai coca về 88 Nguyễn Thị Minh Khai, Q3",
]

_CHAT_PROMPTS = [
    "Shop ơi đơn hàng #DH-9921 của em đã xuất kho chưa ạ?",
    "Sản phẩm áo khoác dù 2 lớp bên mình còn size XL màu đen không shop?",
    "Cho em hỏi thời gian giao hàng dự kiến tới Đà Nẵng là bao lâu vậy ạ?",
    "Chính sách đổi trả sản phẩm khi không vừa size của shop như thế nào ạ?",
]

_TRIAGE_PROMPTS = [
    "Gói hàng tôi nhận được bị rách vỏ hộp và ướt bên trong, yêu cầu hỗ trợ hoàn tiền",
    "Shipper thái độ không tốt và bắt tôi ra đầu hẻm lấy hàng lúc trời mưa",
    "Tôi đã thanh toán chuyển khoản qua MoMo nhưng đơn hàng vẫn báo chưa thanh toán",
]


def make_prompt(route: str, rng: random.Random) -> list[dict[str, str]]:
    if route == "order.extract":
        text = rng.choice(_ORDER_PROMPTS)
    elif route == "support.triage":
        text = rng.choice(_TRIAGE_PROMPTS)
    else:
        text = rng.choice(_CHAT_PROMPTS)

    return [{"role": "user", "content": text}]
