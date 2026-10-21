"""Runner cho pipeline trên nguồn dữ liệu llm-bench (`bench_ts`) — phần DE-1.3.

A14 rebuild `baselines` (.hour-of-week chạy 1 lần/ngày, ví dụ từ Sentinel), A15 tìm
các cửa sổ sự cố thật để replay (S6) và để prior cho mock-llm.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import BASELINES, BENCH_TS
from reflex_mongo.pipelines import a14_baselines, a15_bench_incidents


async def rebuild_baselines(
    db: AsyncDatabase, *, days: int = 60, now: datetime | None = None
) -> int:
    """A14: rebuild `baselines` qua `$merge`, quét `days` ngày gần nhất. Trả về số baseline."""
    pipeline = a14_baselines.build(days=days, now=now)
    await (await db[BENCH_TS].aggregate(pipeline)).to_list(None)
    return await db[BASELINES].count_documents({})


async def top_incidents(
    db: AsyncDatabase,
    *,
    days: int = 7,
    threshold: float = 0.5,
    limit: int = 10,
    from_: datetime | None = None,
    to: datetime | None = None,
) -> list[dict[str, Any]]:
    """A15: top các cửa sổ lỗi kéo dài (err6h >= `threshold`) trong `days` ngày gần nhất."""
    end = to or datetime.now(tz=UTC)
    start = from_ or (end.replace(minute=0, second=0, microsecond=0) - timedelta(days=days))
    pipeline = a15_bench_incidents.build(from_=start, to=end, threshold=threshold, limit=limit)
    return [dict(row) async for row in (await db[BENCH_TS].aggregate(pipeline))]
