"""Rule-based fallback classifier khi LLM lỗi/timeout hoặc Cortex chết — vẫn propose được
action an toàn. Thuần (không I/O) để cả Cortex lẫn watchdog control-plane cùng dùng.
"""

from __future__ import annotations

from typing import Any

from reflex_core.incident import Recommendation

# Confidence cố định của rule engine (cortex-agent.md §2): luôn dưới ngưỡng auto 0.7.
RULES_CONFIDENCE = 0.6


def classify(context_pack: dict[str, Any]) -> Recommendation | None:
    """Phân loại nguyên nhân và đưa ra hành động tương ứng dựa trên bảng quy tắc."""
    incident = context_pack.get("incident", {})
    target = incident.get("target") or context_pack.get("target") or "vendorA:large"
    routes = incident.get("routes") or []
    route = routes[0] if routes else context_pack.get("route") or "order.extract"
    sli = incident.get("sli") or context_pack.get("sli") or "quality"

    # Lấy danh sách candidates từ policy nếu có để tìm target đích
    policy = context_pack.get("policy", {})
    candidates = policy.get("candidates", [])
    other_targets = [c.get("target") for c in candidates if c.get("target") != target]
    fallback_target = other_targets[0] if other_targets else "vendorB:fallback"

    # Kiểm tra tín hiệu từ các signals
    signals = incident.get("signals", [])
    any_truncation = False
    any_rate_limit = False
    any_down = False

    for sig in signals:
        diag = str(sig.get("diagnosis", "")).lower()
        if "truncat" in diag or "length" in diag:
            any_truncation = True
        elif "rate" in diag or "429" in diag:
            any_rate_limit = True
        elif "down" in diag or "50" in diag:
            any_down = True

    # 1. Quality degradation / output truncation
    if sli == "quality" or any_truncation:
        return Recommendation(
            action_type="shift_weight",
            params={
                "route": route,
                "from": target,
                "to": fallback_target,
                "pct": 1.0,
            },
            expected_effect={"quality_5m": ">= 0.99 trong 3m"},
        )

    # 2. Provider down
    if any_down:
        return Recommendation(
            action_type="open_circuit_global",
            params={"target": target, "duration_s": 300},
            expected_effect={"availability": "1.0"},
        )

    # 3. Rate limit storm
    if any_rate_limit:
        return Recommendation(
            action_type="set_concurrency",
            params={"route": route, "target": target, "limit": 20},
            expected_effect={"error_rate": "<= 0.01"},
        )

    # 4. Latency / TTFT
    if sli in ("latency", "ttft"):
        return Recommendation(
            action_type="enable_hedging",
            params={"route": route, "max_cost": 0.05},
            expected_effect={"p95_ttft": "<= 1000ms"},
        )

    # 5. Mặc định: page human
    return Recommendation(
        action_type="page_human",
        params={"reason": "Anomaly detected without matching rule"},
        expected_effect={},
    )
