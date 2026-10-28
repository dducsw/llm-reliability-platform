"""SE-9.2 — Load test gateway: open-loop N rps × T phút, đo overhead gateway.

Open-loop (gửi theo lịch cố định, không chờ response) để không che latency khi gateway chậm.
Overhead lấy từ header `x-reflex-overhead-ms` (wall − upstream), không phải latency end-to-end.

    uv run python tools/loadtest.py --rps 50 --minutes 30 \\
        --gateway http://localhost:8080 --gateway http://localhost:8081 --out loadtest.json

Request quá REQUEST_DEADLINE_S bị tính `client_timeout`; in-flight vượt `rps × STALL_S` (request không
còn tới gateway, vd Docker Desktop nghẽn) → dừng sớm, `aborted` ghi lý do, vẫn xuất kết quả đã đo.

Có MONGODB_URI → ghi thêm dbStats và số document requests_ts/attempts_ts trước/sau (chi phí Mongo).
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

REQUEST_DEADLINE_S = 70  # 2 gateway × timeout 30s + dư
STALL_S = 60

ROUTES = {"order.extract": 0.5, "chat.reply": 0.35, "support.triage": 0.15}
PROMPTS = {
    "order.extract": "Trích xuất đơn hàng: 2 áo thun size M giao tới Quận 3, thanh toán COD.",
    "chat.reply": "Shop ơi đơn của mình khi nào giao vậy?",
    "support.triage": "Khách báo nhận sai màu sản phẩm, muốn đổi trả.",
}


@dataclass
class Stats:
    latency_ms: list[float] = field(default_factory=list)
    overhead_ms: list[float] = field(default_factory=list)
    status: dict[str, int] = field(default_factory=dict)
    late_sends: int = 0
    aborted: str | None = None
    elapsed_s: float = 0.0

    def add_status(self, key: str) -> None:
        self.status[key] = self.status.get(key, 0) + 1


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, int(p / 100 * len(s)))], 2)


async def one(
    client: httpx.AsyncClient, gateways: list[str], route: str, stats: Stats, rid: str
) -> None:
    body = {"messages": [{"role": "user", "content": PROMPTS[route]}]}
    headers = {"x-reflex-route": route, "x-reflex-request-id": rid, "x-priority": "1"}
    t0 = time.perf_counter()
    # Client failover như SDK của app: gateway đầu lỗi kết nối → thử gateway kế tiếp
    for gw in gateways:
        try:
            r = await client.post(f"{gw}/v1/chat/completions", json=body, headers=headers)
        except httpx.TransportError:
            continue
        stats.latency_ms.append((time.perf_counter() - t0) * 1000)
        stats.add_status(str(r.status_code))
        if "x-reflex-overhead-ms" in r.headers:
            stats.overhead_ms.append(float(r.headers["x-reflex-overhead-ms"]))
        return
    stats.add_status("conn_error")


async def run(gateways: list[str], rps: float, seconds: float, seed: int) -> Stats:
    rng = random.Random(seed)
    routes, weights = list(ROUTES), list(ROUTES.values())
    stats = Stats()
    limits = httpx.Limits(max_connections=int(rps * 4), max_keepalive_connections=int(rps * 2))
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        tasks: set[asyncio.Task[None]] = set()
        start = time.perf_counter()
        rotation = itertools.cycle(range(len(gateways)))
        last_report = start
        for i in itertools.count():
            due = start + i / rps
            if due - start >= seconds:
                break
            delay = due - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            elif delay < -0.05:
                stats.late_sends += 1  # máy load test không theo kịp lịch
            k = next(rotation)
            order = gateways[k:] + gateways[:k]
            route = rng.choices(routes, weights)[0]
            t = asyncio.create_task(guarded(client, order, route, stats, f"lt-{seed}-{i}"))
            tasks.add(t)
            t.add_done_callback(tasks.discard)
            now = time.perf_counter()
            if len(tasks) > rps * STALL_S:
                stats.aborted = f"stalled: {len(tasks)} in flight at {now - start:.0f}s"
                print(stats.aborted, file=sys.stderr)
                for t in tasks:
                    t.cancel()
                break
            if now - last_report >= 30:
                last_report = now
                print(
                    f"[{now - start:6.0f}s] sent={i + 1} in_flight={len(tasks)} "
                    f"p99_overhead={pct(stats.overhead_ms, 99)}ms status={stats.status}",
                    file=sys.stderr,
                )
        await asyncio.gather(*tasks, return_exceptions=True)
        stats.elapsed_s = time.perf_counter() - start
    return stats


async def guarded(
    client: httpx.AsyncClient, gateways: list[str], route: str, stats: Stats, rid: str
) -> None:
    try:
        await asyncio.wait_for(one(client, gateways, route, stats, rid), REQUEST_DEADLINE_S)
    except TimeoutError:
        stats.add_status("client_timeout")


def summarize(stats: Stats, rps: float, seconds: float, max_p99_overhead: float) -> dict[str, Any]:
    total = sum(stats.status.values())
    ok = stats.status.get("200", 0)
    p99 = pct(stats.overhead_ms, 99)
    ran = min(seconds, stats.elapsed_s) if stats.elapsed_s else seconds
    return {
        "target_rps": rps,
        "duration_s": seconds,
        "ran_s": round(ran, 1),
        "aborted": stats.aborted,
        "requests": total,
        "achieved_rps": round(total / ran, 2) if ran else 0,
        "success_ratio": round(ok / total, 4) if total else 0,
        "status": stats.status,
        "late_sends": stats.late_sends,
        "latency_ms": {
            p: pct(stats.latency_ms, q) for p, q in (("p50", 50), ("p95", 95), ("p99", 99))
        },
        "overhead_ms": {
            p: pct(stats.overhead_ms, q) for p, q in (("p50", 50), ("p95", 95), ("p99", 99))
        },
        "overhead_samples": len(stats.overhead_ms),
        "max_p99_overhead_ms": max_p99_overhead,
        "pass": stats.aborted is None and p99 is not None and p99 <= max_p99_overhead,
    }


def mongo_snapshot() -> dict[str, Any] | None:
    """dbStats + số document telemetry: chênh lệch trước/sau = chi phí Mongo của load test."""
    uri = os.getenv("MONGODB_URI")
    if not uri:
        return None
    from pymongo import MongoClient

    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        db = client[os.getenv("MONGODB_DB", "reflex")]
        st = db.command("dbStats")
        return {
            "data_mb": round(st.get("dataSize", 0) / 1e6, 3),
            "storage_mb": round(st.get("storageSize", 0) / 1e6, 3),
            "index_mb": round(st.get("indexSize", 0) / 1e6, 3),
            "requests_ts": db["requests_ts"].estimated_document_count(),
            "attempts_ts": db["attempts_ts"].estimated_document_count(),
        }


def mongo_delta(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not before or not after:
        return None
    return {k: round(after[k] - before[k], 3) for k in before}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--gateway", action="append", help="lặp lại cho nhiều gateway")
    ap.add_argument("--rps", type=float, default=50)
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-p99-overhead-ms", type=float, default=10.0)
    ap.add_argument("--out", help="ghi summary JSON")
    args = ap.parse_args()
    gateways = args.gateway or ["http://localhost:8080"]
    seconds = args.minutes * 60

    before = mongo_snapshot()
    stats = asyncio.run(run(gateways, args.rps, seconds, args.seed))
    summary = summarize(stats, args.rps, seconds, args.max_p99_overhead_ms)
    summary["mongo"] = {"before": before, "delta": mongo_delta(before, mongo_snapshot())}
    text = json.dumps(summary, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    sys.exit(0 if summary["pass"] else 1)


if __name__ == "__main__":
    main()
