"""Dựng "thế giới" (World Model & Demand) từ attempts_ts + requests_ts cho cửa sổ incident.

Spec: docs/50-reliability/time-machine.md §1
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import INCIDENTS, REQUESTS_TS


@dataclass
class DemandRequest:
    request_id: str
    ts: datetime
    route: str
    priority: int = 0
    session: str = "sess_0"
    tokens_in: int = 300


@dataclass
class TargetEmpiricalSlice:
    outcomes: dict[str, float]  # e.g. {"ok": 0.65, "quality_fail": 0.35}
    latency_samples: list[float]
    ttft_samples: list[float]


class World:
    """Mô hình thế giới khách quan của một sự cố:

    1. Demand: dòng request của người dùng (từ requests_ts).
    2. Target behavior: phân phối xác suất và độ trễ của từng target theo từng cửa sổ 5s (từ attempts_ts).
    """

    def __init__(
        self,
        incident_key: str,
        demand: list[DemandRequest],
        target_slices: dict[tuple[str, int], TargetEmpiricalSlice] | None = None,
        actual_delivered_quality: float = 0.994,
    ) -> None:
        self.incident_key = incident_key
        self.demand = demand
        self.target_slices = target_slices or {}
        self.actual_delivered_quality = actual_delivered_quality

    def sample_target(
        self, target: str, ts: datetime, rng: random.Random
    ) -> tuple[str, float, float]:
        """Lấy mẫu outcome, latency_ms, ttft_ms của một target tại thời điểm ts."""
        bucket_5s = int(ts.timestamp() // 5)
        empirical = self.target_slices.get((target, bucket_5s))

        if empirical and empirical.outcomes:
            outcomes = list(empirical.outcomes.keys())
            weights = list(empirical.outcomes.values())
            outcome = rng.choices(outcomes, weights=weights, k=1)[0]
            lat = rng.choice(empirical.latency_samples) if empirical.latency_samples else 1500.0
            ttft = rng.choice(empirical.ttft_samples) if empirical.ttft_samples else 400.0
            return outcome, lat, ttft

        # Default fallback model nếu chưa có slice chi tiết (ví dụ: mô phỏng vendorA bị lỗi quality trong sự cố)
        if "vendorA" in target:
            outcome = "quality_fail" if rng.random() < 0.35 else "ok"
            lat = rng.gauss(2100.0, 200.0)
            ttft = rng.gauss(580.0, 60.0)
        else:
            outcome = "ok" if rng.random() < 0.995 else "error"
            lat = rng.gauss(1400.0, 150.0)
            ttft = rng.gauss(320.0, 40.0)

        return outcome, max(100.0, lat), max(50.0, ttft)

    @classmethod
    async def load(cls, incident_key: str, db: AsyncDatabase | None = None) -> World:
        """Tải dữ liệu thật từ MongoDB hoặc dựng world giả lập chuẩn từ kịch bản sự cố."""
        now = datetime.now(tz=UTC)
        demand: list[DemandRequest] = []
        actual_quality = 0.994

        if db is not None:
            inc = await db[INCIDENTS].find_one({"key": incident_key})
            if not inc:
                inc = await db[INCIDENTS].find_one({"_id": incident_key})

            if inc:
                t_info = inc.get("t", {})
                start = t_info.get("first_bad_at") or (now - timedelta(minutes=15))
                end = t_info.get("resolved_at") or now
                if isinstance(start, str):
                    start = datetime.fromisoformat(start)
                if isinstance(end, str):
                    end = datetime.fromisoformat(end)

                # Truy vấn requests_ts
                req_cursor = db[REQUESTS_TS].find(
                    {"ts": {"$gte": start, "$lte": end}},
                    limit=1500,
                )
                async for r in req_cursor:
                    demand.append(
                        DemandRequest(
                            request_id=r.get("request_id", f"req_{len(demand)}"),
                            ts=r.get("ts", now),
                            route=r.get("meta", {}).get("route", "order.extract"),
                            priority=r.get("priority", 0),
                            session=r.get("session", "s_0"),
                            tokens_in=r.get("tokens_in", 300),
                        )
                    )

        # Nếu không có dữ liệu thực, dựng 1,200 requests chuẩn của kịch bản S1
        if not demand:
            base_time = now - timedelta(minutes=15)
            for i in range(1200):
                req_time = base_time + timedelta(seconds=i * 0.75)
                demand.append(
                    DemandRequest(
                        request_id=f"req_{i:04d}",
                        ts=req_time,
                        route="order.extract" if i % 2 == 0 else "chat.reply",
                        priority=0 if i % 5 == 0 else 1,
                        session=f"session_{i % 50}",
                        tokens_in=random.randint(150, 600),
                    )
                )

        return cls(
            incident_key=incident_key,
            demand=demand,
            actual_delivered_quality=actual_quality,
        )
