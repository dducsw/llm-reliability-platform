from __future__ import annotations

from typing import Any


def score(prediction: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, float]:
    """Tính toán các chỉ số đánh giá độ chính xác của Cortex:

    - side_acc: Độ chính xác phân biệt phía lỗi (provider vs gateway)
    - cause_acc: Độ chính xác phân loại nguyên nhân gốc rễ (cause_class)
    - action_acc: Độ chính xác đề xuất loại hành động xử lý (action_type)
    - overall_score: Điểm tổng hợp có trọng số
    """
    pred_side = str(prediction.get("side", "")).lower()
    gt_side = str(ground_truth.get("side", "")).lower()
    side_acc = 1.0 if (pred_side and pred_side == gt_side) else 0.0

    pred_cause = str(prediction.get("cause_class", prediction.get("hypothesis", ""))).lower()
    gt_cause = str(ground_truth.get("cause_class", "")).lower()
    cause_acc = 1.0 if (gt_cause and (gt_cause in pred_cause or pred_cause in gt_cause)) else 0.0

    pred_action = str(
        prediction.get("action_type", prediction.get("action", {}).get("type", ""))
    ).lower()
    gt_action = str(ground_truth.get("action_type", "")).lower()
    action_acc = 1.0 if (gt_action and gt_action == pred_action) else 0.0

    confidence = float(prediction.get("confidence", 1.0))
    overall_score = 0.3 * side_acc + 0.35 * cause_acc + 0.35 * action_acc

    return {
        "side_acc": side_acc,
        "cause_acc": cause_acc,
        "action_acc": action_acc,
        "confidence": confidence,
        "overall_score": round(overall_score, 4),
    }
