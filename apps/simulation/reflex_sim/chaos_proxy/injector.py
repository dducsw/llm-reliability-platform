"""Áp fault lên response (non-stream) hoặc stream chunks."""

from __future__ import annotations

import json
import random
from typing import Any

from reflex_sim.chaos_proxy.faults import Fault, FaultType


def select(faults: list[Fault], target: str, route: str | None, rng: random.Random) -> list[Fault]:
    """Chọn danh sách fault khớp với target/route và tỉ lệ traffic."""
    selected: list[Fault] = []
    for f in faults:
        sel = f.selector
        if sel.target and sel.target != target:
            continue
        if sel.route and route and sel.route != route:
            continue
        prob = f.params.get("probability", 1.0)
        if sel.pct_of_traffic is not None:
            prob = sel.pct_of_traffic
        if rng.random() <= prob:
            selected.append(f)
    return selected


def apply(fault: Fault, response: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Áp dụng fault lên response OpenAI-compatible dict."""
    res = json.loads(json.dumps(response))  # deep copy
    choices = res.get("choices", [{}])
    choice = choices[0] if choices else {}
    message = choice.get("message", {})
    content = message.get("content", "")

    if fault.type == FaultType.TRUNCATE:
        keep_ratio_param = fault.params.get("keep_ratio", 0.5)
        if isinstance(keep_ratio_param, (list, tuple)):
            ratio = rng.uniform(float(keep_ratio_param[0]), float(keep_ratio_param[1]))
        else:
            ratio = float(keep_ratio_param)
        keep_len = max(5, int(len(content) * ratio))
        message["content"] = content[:keep_len]
        choice["finish_reason"] = "length"

    elif fault.type == FaultType.CORRUPT_JSON:
        mode = fault.params.get("mode", "drop_brace")
        if mode == "drop_brace" and content.endswith("}"):
            message["content"] = content[:-1]
        elif mode == "wrong_type":
            # Thay đổi một trường thành sai kiểu
            message["content"] = content.replace('"qty": 2', '"qty": "invalid_two"')
        else:
            message["content"] = content[: len(content) // 2]
        choice["finish_reason"] = "stop"

    elif fault.type == FaultType.EMPTY:
        message["content"] = ""
        choice["finish_reason"] = "stop"

    elif fault.type == FaultType.REFUSAL:
        phrase = fault.params.get("phrase", "Xin lỗi, tôi không thể thực hiện yêu cầu này vì vi phạm chính sách.")
        message["content"] = phrase
        choice["finish_reason"] = "stop"

    elif fault.type == FaultType.ERROR:
        status = int(fault.params.get("status", 500))
        return {
            "status_code": status,
            "error": {"message": "Chaos injected error", "type": "server_error", "code": status},
        }

    elif fault.type == FaultType.RATE_LIMIT:
        retry_after = fault.params.get("retry_after_s", 2)
        return {
            "status_code": 429,
            "retry_after": retry_after,
            "error": {"message": "Rate limit exceeded", "type": "rate_limit_error", "code": 429},
        }

    return res
