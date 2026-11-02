"""Dựng "thế giới" (World Model & Demand) từ attempts_ts + requests_ts cho cửa sổ incident.

Spec: docs/50-reliability/time-machine.md §1

- Cửa sổ: từ lúc lỗi bắt đầu thật (attempt hỏng đầu tiên của target sự cố trên route, tìm lùi
  `ONSET_LOOKBACK` trước `detected_at`) tới `resolved_at`.
- Demand: request thật (không synthetic) của các route trong incident.
- World: mỗi (target, bucket 5s) → phân phối outcome + mẫu latency/TTFT thực nghiệm, gom bằng một
  aggregation trên `attempts_ts`. Bucket trống (vd target bị rút traffic sau mitigation) lấy bucket
  gần nhất trong ±`NEAREST_BUCKETS`, rồi tới phân phối gộp cả cửa sổ của target; `coverage` cho biết
  tỷ lệ lấy mẫu trúng bucket thật.
- Không có DB / không có telemetry → world synthetic của S1 (`source="synthetic"`).
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import ATTEMPTS_TS, INCIDENTS, REQUESTS_TS

BUCKET_S = 5
NEAREST_BUCKETS = 12  # ±60s
ONSET_LOOKBACK = timedelta(minutes=15)
SAMPLES_PER_BUCKET = 30
DEFAULT_PRIMARY = "vendorA:large"
DEFAULT_SECONDARY = "vendorB:large"


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


@dataclass
class WorldStats:
    hits_exact: int = 0
    hits_nearest: int = 0
    hits_pooled: int = 0
    hits_synthetic: int = 0
    by_target: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def coverage(self) -> float:
        total = self.hits_exact + self.hits_nearest + self.hits_pooled + self.hits_synthetic
        return round(self.hits_exact / total, 4) if total else 0.0


def _bucket(ts: datetime) -> int:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return int(ts.timestamp() // BUCKET_S)


def _slice(outcomes: dict[str, int], lat: list[float], ttft: list[float]) -> TargetEmpiricalSlice:
    total = sum(outcomes.values()) or 1
    return TargetEmpiricalSlice(
        outcomes={k: v / total for k, v in outcomes.items()},
        latency_samples=[x for x in lat if x is not None],
        ttft_samples=[x for x in ttft if x is not None],
    )


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
        *,
        primary_target: str = DEFAULT_PRIMARY,
        secondary_target: str = DEFAULT_SECONDARY,
        pooled: dict[str, TargetEmpiricalSlice] | None = None,
        mitigated_at: datetime | None = None,
        window: tuple[datetime, datetime] | None = None,
        source: str = "synthetic",
    ) -> None:
        self.incident_key = incident_key
        self.demand = demand
        self.target_slices = target_slices or {}
        self.actual_delivered_quality = actual_delivered_quality
        self.primary_target = primary_target
        self.secondary_target = secondary_target
        self.pooled = pooled or {}
        self.mitigated_at = mitigated_at
        self.window = window
        self.source = source
        self.stats = WorldStats()

    def _empirical(self, target: str, bucket: int) -> TargetEmpiricalSlice | None:
        hit = self.target_slices.get((target, bucket))
        if hit is not None:
            self.stats.hits_exact += 1
            return hit
        for d in range(1, NEAREST_BUCKETS + 1):
            for b in (bucket - d, bucket + d):
                hit = self.target_slices.get((target, b))
                if hit is not None:
                    self.stats.hits_nearest += 1
                    return hit
        hit = self.pooled.get(target)
        if hit is not None:
            self.stats.hits_pooled += 1
        return hit

    def sample_target(
        self, target: str, ts: datetime, rng: random.Random
    ) -> tuple[str, float, float]:
        """Lấy mẫu outcome, latency_ms, ttft_ms của một target tại thời điểm ts."""
        self.stats.by_target[target] += 1
        empirical = self._empirical(target, _bucket(ts))

        if empirical and empirical.outcomes:
            outcomes = list(empirical.outcomes.keys())
            weights = list(empirical.outcomes.values())
            outcome = rng.choices(outcomes, weights=weights, k=1)[0]
            lat = rng.choice(empirical.latency_samples) if empirical.latency_samples else 1500.0
            ttft = rng.choice(empirical.ttft_samples) if empirical.ttft_samples else 400.0
            return outcome, lat, ttft

        # World synthetic của S1 (không có telemetry): primary bị lỗi quality 35%, secondary khỏe.
        self.stats.hits_synthetic += 1
        if target == self.primary_target:
            outcome = "quality_fail" if rng.random() < 0.35 else "ok"
            lat = rng.gauss(2100.0, 200.0)
            ttft = rng.gauss(580.0, 60.0)
        else:
            outcome = "ok" if rng.random() < 0.995 else "error"
            lat = rng.gauss(1400.0, 150.0)
            ttft = rng.gauss(320.0, 40.0)

        return outcome, max(100.0, lat), max(50.0, ttft)

    def describe(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "window": [w.isoformat() for w in self.window] if self.window else None,
            "demand": len(self.demand),
            "primary_target": self.primary_target,
            "secondary_target": self.secondary_target,
            "mitigated_at": self.mitigated_at.isoformat() if self.mitigated_at else None,
            "buckets": len(self.target_slices),
            "actual_delivered_quality": self.actual_delivered_quality,
        }

    @classmethod
    async def load(cls, incident_key: str, db: AsyncDatabase | None = None) -> World:
        """Tải dữ liệu thật từ MongoDB hoặc dựng world giả lập chuẩn từ kịch bản sự cố."""
        if db is not None:
            inc = await db[INCIDENTS].find_one({"key": incident_key})
            if not inc:
                inc = await db[INCIDENTS].find_one({"_id": incident_key})
            if inc:
                world = await cls._from_mongo(incident_key, inc, db)
                if world is not None:
                    return world
        return cls._synthetic(incident_key)

    @classmethod
    def _synthetic(cls, incident_key: str) -> World:
        """1 200 request chuẩn của kịch bản S1 khi không có dữ liệu thật."""
        rng = random.Random(incident_key)
        base_time = datetime.now(tz=UTC) - timedelta(minutes=15)
        demand = [
            DemandRequest(
                request_id=f"req_{i:04d}",
                ts=base_time + timedelta(seconds=i * 0.75),
                route="order.extract" if i % 2 == 0 else "chat.reply",
                priority=0 if i % 5 == 0 else 1,
                session=f"session_{i % 50}",
                tokens_in=rng.randint(150, 600),
            )
            for i in range(1200)
        ]
        return cls(incident_key=incident_key, demand=demand)

    @classmethod
    async def _from_mongo(
        cls, incident_key: str, inc: dict[str, Any], db: AsyncDatabase
    ) -> World | None:
        t = inc.get("t") or {}
        detected = t.get("detected_at") or t.get("first_bad_at")
        if detected is None:
            return None
        primary = inc.get("target") or DEFAULT_PRIMARY
        routes = list(inc.get("routes") or [])
        route_q: dict[str, Any] = {"route": {"$in": routes}} if routes else {}
        end = t.get("resolved_at") or datetime.now(tz=UTC)

        # Onset thật: attempt hỏng đầu tiên của target sự cố trước khi phát hiện (MTTD thật).
        first_bad = await db[ATTEMPTS_TS].find_one(
            {
                "meta.target": primary,
                "ts": {"$gte": detected - ONSET_LOOKBACK, "$lte": detected},
                "outcome": {"$nin": ["ok", "cancelled"]},
                **route_q,
            },
            sort=[("ts", 1)],
        )
        start = min(first_bad["ts"], detected) if first_bad else (t.get("first_bad_at") or detected)

        # Demand + delivered quality thật (requests_ts) — $match đứng đầu, dùng index meta+ts.
        req_match: dict[str, Any] = {
            "ts": {"$gte": start, "$lte": end},
            "meta.synthetic": {"$ne": True},
        }
        if routes:
            req_match["meta.route"] = {"$in": routes}
        demand: list[DemandRequest] = []
        good = 0
        async for r in db[REQUESTS_TS].find(req_match).sort("ts", 1).limit(20_000):
            demand.append(
                DemandRequest(
                    request_id=r.get("request_id", f"req_{len(demand)}"),
                    ts=r["ts"],
                    route=r.get("meta", {}).get("route", routes[0] if routes else ""),
                    priority=r.get("priority", 0),
                    session=r.get("session") or "s_0",
                    tokens_in=r.get("tokens_in", 300),
                )
            )
            quality = r.get("quality") or {}
            if r.get("outcome") == "ok" and quality.get("pass", True):
                good += 1
        if not demand:
            return None

        # World: (target, bucket 5s) → outcome counts + mẫu latency/TTFT.
        pipeline: list[dict[str, Any]] = [
            {
                "$match": {
                    "ts": {"$gte": start, "$lte": end},
                    "outcome": {"$ne": "cancelled"},
                    **route_q,
                }
            },
            {
                "$group": {
                    "_id": {
                        "target": "$meta.target",
                        "b": {"$dateTrunc": {"date": "$ts", "unit": "second", "binSize": BUCKET_S}},
                        "o": "$outcome",
                    },
                    "n": {"$sum": 1},
                    "lat": {"$firstN": {"input": "$latency_ms", "n": SAMPLES_PER_BUCKET}},
                    "ttft": {"$firstN": {"input": "$ttft_ms", "n": SAMPLES_PER_BUCKET}},
                }
            },
        ]
        counts: dict[tuple[str, int], dict[str, int]] = defaultdict(dict)
        lats: dict[tuple[str, int], list[float]] = defaultdict(list)
        ttfts: dict[tuple[str, int], list[float]] = defaultdict(list)
        pooled_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        pooled_lat: dict[str, list[float]] = defaultdict(list)
        pooled_ttft: dict[str, list[float]] = defaultdict(list)
        async for row in await db[ATTEMPTS_TS].aggregate(pipeline):
            target = row["_id"]["target"]
            key = (target, _bucket(row["_id"]["b"]))
            counts[key][row["_id"]["o"]] = row["n"]
            lats[key].extend(row["lat"])
            ttfts[key].extend(row["ttft"])
            pooled_counts[target][row["_id"]["o"]] += row["n"]
            pooled_lat[target].extend(row["lat"])
            pooled_ttft[target].extend(row["ttft"])

        slices = {k: _slice(v, lats[k], ttfts[k]) for k, v in counts.items()}
        pooled = {
            tg: _slice(dict(c), pooled_lat[tg], pooled_ttft[tg]) for tg, c in pooled_counts.items()
        }
        others = sorted(
            ((sum(c.values()), tg) for tg, c in pooled_counts.items() if tg != primary),
            reverse=True,
        )
        secondary = others[0][1] if others else DEFAULT_SECONDARY

        return cls(
            incident_key=incident_key,
            demand=demand,
            target_slices=slices,
            actual_delivered_quality=round(good / len(demand), 4),
            primary_target=primary,
            secondary_target=secondary,
            pooled=pooled,
            mitigated_at=t.get("mitigated_at"),
            window=(start, end),
            source="mongo",
        )
