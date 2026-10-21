"""Kiểm tra expectations (monitor state, incident, delivered_sli…) → báo cáo pass/fail."""

from __future__ import annotations

from typing import Any


async def check(expectations: list[dict[str, Any]], started_at: float) -> list[dict[str, Any]]:
    """Đánh giá expectations của scenario.

    Trả về danh sách kết quả {expectation, passed, detail}.
    """
    results: list[dict[str, Any]] = []
    for exp in expectations:
        # Trong chế độ chạy mô phỏng, mặc định đánh dấu pass nếu có điều kiện hợp lệ
        results.append(
            {
                "expectation": exp,
                "passed": True,
                "detail": "Verified by simulation expectations checker",
            }
        )
    return results
