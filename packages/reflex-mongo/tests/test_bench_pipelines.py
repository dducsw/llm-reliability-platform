"""Golden test nhỏ cho A14 (baselines) + A15 (sự cố thật) trên bench_ts.

Dữ liệu cố ý nhỏ (16 docs, 2 model) — chạy nhanh, kiểm tra được logic pipeline.
Fixture `it_db` (tests/conftest.py) ref db riêng `reflex_it` trên MONGODB_URI,
drop mỗi test → không đụng db dev.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import BASELINES, BENCH_TS
from reflex_mongo.migrate.collections import ensure_collections
from reflex_mongo.pipelines import a14_baselines, a15_bench_incidents
from reflex_sim.bench.importer import import_bench
from reflex_sim.bench.runners import rebuild_baselines, top_incidents

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 20, 14, 0, tzinfo=UTC)
MODELS = ("anthropic/claude-sonnet-4.5", "openai/gpt-5.5")
TUESDAY = 2  # 2026-10-20 là thứ Ba


def _doc(model: str, hour: int) -> dict:
    """Giờ 12-14 của claude là 'error' (sự cố thật giả lập), còn lại healthy."""
    status = "error" if (model == MODELS[0] and 12 <= hour <= 14) else "healthy"
    return {
        "ts": datetime(2026, 10, 20, hour, 0, tzinfo=UTC),
        "meta": {
            "model": model,
            "vendor": model.split("/")[0],
            "source": "llm-bench-data",
            "route_proto": "openai",
        },
        "status": status,
        "ttft_ms": 300.0 + hour,
        "latency_ms": 2000.0 + hour,
        "tps": 60.0,
        "token_count": 20,
    }


@pytest.fixture()
async def bench_ts(it_db: AsyncDatabase[dict[str, Any]]) -> AsyncDatabase[dict[str, Any]]:
    """Db test sạch (migrate schema) + 16 docs bench_ts: 8 giờ x 2 model."""
    await ensure_collections(it_db)
    await it_db[BENCH_TS].insert_many(
        [_doc(m, hour) for m in MODELS for hour in range(9, 17)], ordered=False
    )
    return it_db


async def test_a14_baselines_hour_of_week(bench_ts: AsyncDatabase[dict[str, Any]]) -> None:
    await (await bench_ts[BENCH_TS].aggregate(a14_baselines.build(days=2, now=NOW))).to_list(None)

    baselines = await bench_ts[BASELINES].find({"_id.model": MODELS[0]}).to_list(None)
    # 8 giờ trong dữ liệu → 8 baseline (model, dow, hour), _id gộp đúng
    assert len(baselines) == 8
    assert all(b["_id"]["dow"] == TUESDAY for b in baselines)
    hour13 = next(b for b in baselines if b["_id"]["hour"] == 13)
    assert hour13["err_ratio"] == 1.0  # giờ 13 mọi sample đều error
    assert hour13["lat_median"] == 2013.0  # 2000 + 13 (median của 1 slot)
    assert hour13["samples"] == 1
    assert "updated_at" in hour13
    # model khoẻ phải có err_ratio == 0
    healthy = await bench_ts[BASELINES].find({"_id.model": MODELS[1]}).to_list(None)
    assert {b["err_ratio"] for b in healthy} == {0.0}


async def test_a15_finds_real_incident_window(bench_ts: AsyncDatabase[dict[str, Any]]) -> None:
    pipeline = a15_bench_incidents.build(
        from_=datetime(2026, 10, 20, tzinfo=UTC), to=datetime(2026, 10, 21, tzinfo=UTC)
    )
    rows = await (await bench_ts[BENCH_TS].aggregate(pipeline)).to_list(None)
    # Chỉ claude có cửa sổ 6h lỗi; err6h tại h14..16 = 3/6 = 0.5 đúng ngưỡng
    assert [(r["_id"], r["worst"], r["hours"]) for r in rows] == [
        (MODELS[0], pytest.approx(0.5), 3)
    ]
    incident = rows[0]
    assert incident["first"] == datetime(2026, 10, 20, 14, tzinfo=UTC)
    assert incident["last"] == datetime(2026, 10, 20, 16, tzinfo=UTC)


async def test_runners_rebuild_and_top_incidents(bench_ts: AsyncDatabase[dict[str, Any]]) -> None:
    """Kiểm tra runner A14 & A15 chạy qua facade `reflex_sim.bench.runners`."""
    count = await rebuild_baselines(bench_ts, days=2, now=NOW)
    assert count == 16  # 8 giờ x 2 models

    incidents = await top_incidents(
        bench_ts,
        days=1,
        threshold=0.5,
        from_=datetime(2026, 10, 20, tzinfo=UTC),
        to=datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert len(incidents) == 1
    assert incidents[0]["_id"] == MODELS[0]
    assert incidents[0]["hours"] == 3


async def test_e2e_import_bench_and_process(
    it_db: AsyncDatabase[dict[str, Any]], tmp_path: Path
) -> None:
    """E2E pipeline: Sample JSONL -> import_bench -> bench_ts -> A14 & A15."""
    await ensure_collections(it_db)

    # Tạo fixture nhỏ: 1 ngày giả lập trong cache_dir
    cache_dir = tmp_path / "cache"
    day_file = cache_dir / "2026-10" / "2026-10-19.jsonl"
    day_file.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    # 4 giờ data cho 2 model
    for h in range(10, 14):
        for m in MODELS:
            status = "error" if (m == MODELS[0] and h >= 12) else "healthy"
            lines.append(
                json.dumps(
                    {
                        "provider": "openai",
                        "model": m,
                        "status": status,
                        "ttft_ms": 250.0 + h,
                        "latency_ms": 1500.0 + h,
                        "tokens_per_sec": 70.0,
                        "token_count": 25,
                        "timestamp": f"2026-10-19T{h:02d}:00:00Z",
                    }
                )
            )
    day_file.write_text("\n".join(lines), encoding="utf-8")

    # Import qua import_bench với until cố định để đọc đúng file vừa tạo
    until = datetime(2026, 10, 20, 12, tzinfo=UTC)
    inserted = await import_bench(
        days=1, cache_dir=cache_dir, collection=it_db[BENCH_TS], until=until
    )
    assert inserted == 8  # 4h x 2 models

    # Chạy pipeline A14 qua runner
    base_count = await rebuild_baselines(it_db, days=2, now=until)
    assert base_count == 8

    # Chạy pipeline A15 qua runner
    incidents = await top_incidents(
        it_db,
        days=1,
        threshold=0.5,
        from_=datetime(2026, 10, 19, tzinfo=UTC),
        to=datetime(2026, 10, 20, tzinfo=UTC),
    )
    assert len(incidents) == 1
    assert incidents[0]["_id"] == MODELS[0]
