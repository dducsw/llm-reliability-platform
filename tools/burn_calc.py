"""Tính thời điểm alert dự kiến cho scenario (burn rate theo profile) — không ước lượng tay.

Spec: docs/50-reliability/slo-and-error-budget.md §5, docs/00-strategy/design-review-v1.md F4.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class AlertProfile:
    name: str
    window_sec: int  # total SLO window in seconds (e.g. 6h = 21600s, 30d = 2592000s)
    long_window_sec: int  # 3m = 180s (demo) or 1h = 3600s (standard)
    short_window_sec: int  # 30s (demo) or 5m = 300s (standard)
    factor: float = 14.4  # page tier factor
    min_samples: int = 30


PROFILES = {
    "demo": AlertProfile(
        name="demo",
        window_sec=6 * 3600,
        long_window_sec=3 * 60,
        short_window_sec=30,
        factor=14.4,
        min_samples=30,
    ),
    "standard": AlertProfile(
        name="standard",
        window_sec=30 * 86400,
        long_window_sec=3600,
        short_window_sec=300,
        factor=14.4,
        min_samples=100,
    ),
}


def time_to_alert(
    fault_rate: float,
    objective: float,
    rps: float,
    profile: AlertProfile,
) -> float:
    """Tính giây t từ khi bắt đầu fault đến khi cả 2 cửa sổ đều burn >= factor và đủ min_samples.

    Trong rolling window W, sau thời gian t (t < W):
      error_rate(t) = (t / W) * fault_rate
      burn_rate(t) = error_rate(t) / (1 - objective)
    Để burn_rate >= factor:
      t >= (factor * (1 - objective) * W) / fault_rate
    """
    error_budget = 1.0 - objective
    if fault_rate <= 0 or error_budget <= 0:
        return float("inf")

    # Thời gian để short window đạt burn factor
    t_short = (profile.factor * error_budget * profile.short_window_sec) / fault_rate
    # Thời gian để long window đạt burn factor
    t_long = (profile.factor * error_budget * profile.long_window_sec) / fault_rate
    # Thời gian để tích luỹ đủ min_samples
    t_samples = profile.min_samples / rps if rps > 0 else float("inf")

    # Multi-window cần cả short window lẫn long window thoả mãn
    t_burn = max(t_short, t_long)
    return max(t_burn, t_samples)


def calculate_scenarios(profile_name: str = "demo") -> list[dict[str, float | str]]:
    p = PROFILES[profile_name]
    scenarios = [
        {"name": "S1: Silent Brownout", "fault": 0.35, "obj": 0.99, "rps": 8.0},
        {"name": "S2: 429 Storm", "fault": 0.70, "obj": 0.99, "rps": 8.0},
        {"name": "S3: Cascade Brownout", "fault": 0.50, "obj": 0.99, "rps": 8.0},
        {"name": "S4: Latency Degradation", "fault": 0.40, "obj": 0.99, "rps": 8.0},
        {"name": "S5: Severe Outage", "fault": 1.00, "obj": 0.99, "rps": 8.0},
    ]

    results = []
    for sc in scenarios:
        sec = time_to_alert(float(sc["fault"]), float(sc["obj"]), float(sc["rps"]), p)
        # Làm tròn lên chu kỳ tick 10s của Sentinel
        tick_sec = math.ceil(sec / 10.0) * 10
        results.append(
            {
                "scenario": sc["name"],
                "fault_rate": sc["fault"],
                "exact_sec": round(sec, 1),
                "tick_sec": tick_sec,
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Tính thời điểm alert theo burn rate")
    parser.add_argument("--profile", default="demo", choices=["demo", "standard"])
    parser.add_argument("--fault", type=float, default=None, help="Tỉ lệ lỗi (0.0-1.0)")
    parser.add_argument("--objective", type=float, default=0.99, help="SLO objective (vd: 0.99)")
    parser.add_argument("--rps", type=float, default=8.0, help="Requests per second")
    args = parser.parse_args()

    prof = PROFILES[args.profile]
    if args.fault is not None:
        t = time_to_alert(args.fault, args.objective, args.rps, prof)
        tick = math.ceil(t / 10.0) * 10
        print(f"Profile: {prof.name}")
        print(
            f"Fault: {args.fault * 100:.1f}%, Objective: {args.objective * 100:.1f}%, RPS: {args.rps}"
        )
        print(f"Exact alert time: {t:.1f}s -> Sentinel tick: {tick}s")
        return

    print(f"=== BẢNG TÍNH THỜI ĐIỂM ALERT (Profile: {prof.name.upper()}) ===")
    print(f"{'Kịch bản':<25} | {'Fault':<8} | {'Toán học':<10} | {'Sentinel Tick':<14}")
    print("-" * 65)
    for res in calculate_scenarios(args.profile):
        print(
            f"{res['scenario']:<25} | {float(res['fault_rate']) * 100:>5.1f}% | {res['exact_sec']:>7.1f}s | {res['tick_sec']:>10.0f}s"
        )


if __name__ == "__main__":
    main()
