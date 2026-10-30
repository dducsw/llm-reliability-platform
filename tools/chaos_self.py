"""SE-9.1 — Chaos lên chính Reflex: tắt từng thành phần, xác nhận fail-safe.

Mỗi thí nghiệm: dừng một service compose → bắn traffic qua cả hai gateway (client failover)
→ so tỉ lệ thành công với ngưỡng → khởi động lại. Kỳ vọng (system-architecture.md §4):

| Dừng            | Kỳ vọng                                                            |
| mongo           | gateway phục vụ bằng policy snapshot; telemetry rơi, request không   |
| datadog-agent   | DogStatsD/APM fire-and-forget, không ảnh hưởng request              |
| cortex          | data path không phụ thuộc Cortex                                    |
| control-plane   | gateway giữ policy cuối, không cần control-plane để phục vụ         |
| gateway-1       | client failover sang gateway-2                                      |

    uv run python tools/chaos_self.py                       # cả 5 thí nghiệm
    uv run python tools/chaos_self.py --only mongo --seconds 120
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from loadtest import run

COMPOSE = ["docker", "compose", "--env-file", ".env", "-f", "infra/compose/docker-compose.yml"]
GATEWAYS = ["http://localhost:8080", "http://localhost:8081"]
EXPERIMENTS: dict[str, float] = {  # service → success ratio tối thiểu khi service đó chết
    "mongo": 0.95,
    "datadog-agent": 0.99,
    "cortex": 0.99,
    "control-plane": 0.99,
    "gateway-1": 0.99,
}


def compose(*args: str) -> None:
    subprocess.run([*COMPOSE, *args], check=True, capture_output=True)


def wait_healthy(timeout_s: float = 90) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if all(httpx.get(f"{g}/healthz", timeout=2).status_code == 200 for g in GATEWAYS):
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


def experiment(service: str, min_ok: float, rps: float, seconds: float) -> dict[str, object]:
    print(f"── {service}: stop, {rps} rps × {seconds:.0f}s", file=sys.stderr)
    baseline = asyncio.run(run(GATEWAYS, rps, 10, seed=1))
    compose("stop", service)
    try:
        stats = asyncio.run(run(GATEWAYS, rps, seconds, seed=2))
    finally:
        compose("start", service)
    recovered = wait_healthy()
    total = sum(stats.status.values())
    ok = stats.status.get("200", 0) / total if total else 0.0
    base_total = sum(baseline.status.values())
    return {
        "service": service,
        "baseline_ok": round(baseline.status.get("200", 0) / base_total, 4) if base_total else 0,
        "during_ok": round(ok, 4),
        "status": stats.status,
        "min_ok": min_ok,
        "recovered": recovered,
        "pass": ok >= min_ok and recovered,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--only", action="append", choices=list(EXPERIMENTS))
    ap.add_argument("--rps", type=float, default=10)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--out", help="ghi kết quả JSON")
    args = ap.parse_args()

    if not wait_healthy(10):
        sys.exit("Gateways not healthy — chạy `task up` trước.")
    results = [
        experiment(svc, EXPERIMENTS[svc], args.rps, args.seconds)
        for svc in (args.only or EXPERIMENTS)
    ]
    text = json.dumps(results, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    sys.exit(0 if all(r["pass"] for r in results) else 1)


if __name__ == "__main__":
    main()
