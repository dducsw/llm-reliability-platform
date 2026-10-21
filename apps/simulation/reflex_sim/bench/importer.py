"""Importer cho dataset public Jwrede/llm-bench-data (CC0).

Luồng (docs/20-architecture/simulation-and-chaos.md §4):
1. Tải `data/YYYY-MM/YYYY-MM-DD.jsonl` cho từng ngày cần (cache ở `cache_dir`, skip file đã có).
2. Chuẩn hóa từng dòng → document `bench_ts`.
3. Dedup phía client theo (model, ts) — Time Series không có unique index.
4. Sắp theo (meta.model, ts), `insertMany(ordered=False)` theo batch 1000
   (cùng nguồn đi cùng nhau, cũ trước mới sau).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from pymongo.asynchronous.collection import AsyncCollection

logger = logging.getLogger(__name__)

REPO_RAW = "https://raw.githubusercontent.com/Jwrede/llm-bench-data/main/data"
BATCH_SIZE = 1000
SOURCE = "llm-bench-data"

# Chỉ những field hợp lệ của source mới được ghi vào bench_ts (mongodb-data-model.md §2.4)
_TEXT_FIELDS = ("status",)
_FLOAT_FIELDS = ("ttft_ms", "latency_ms", "tokens_per_sec")
_INT_FIELDS = ("token_count",)


def date_range(days: int, *, until: datetime | None = None) -> Iterator[datetime]:
    """Các ngày (00:00 UTC) trong `days` ngày lại, trừ hôm nay (file hôm nay có thể chưa đủ)."""
    end = (until or datetime.now(tz=UTC)).astimezone(UTC).date() - timedelta(days=1)
    for offset in range(days - 1, -1, -1):
        yield datetime.combine(end, datetime.min.time(), tzinfo=UTC) - timedelta(days=offset)


def _rel_path(day: datetime) -> str:
    return f"{day:%Y-%m}/{day:%Y-%m-%d}.jsonl"


def _local_path(cache_dir: Path, day: datetime) -> Path:
    return cache_dir / f"{day:%Y-%m}" / f"{day:%Y-%m-%d}.jsonl"


async def _fetch_files(
    days: int,
    cache_dir: str | Path,
    *,
    client: httpx.AsyncClient | None = None,
    until: datetime | None = None,
) -> tuple[Path, ...]:
    """Tải từng file ngày vào cache; không fail khi một file chưa có (dataset lag vài giờ)."""
    dir_path = Path(cache_dir)
    await asyncio.to_thread(dir_path.mkdir, parents=True, exist_ok=True)
    paths: list[Path] = []

    async with client or httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
        for day in date_range(days, until=until):
            dest = _local_path(dir_path, day)
            if dest.exists():
                paths.append(dest)
                continue
            resp = await http.get(f"{REPO_RAW}/{_rel_path(day)}")
            if resp.status_code == 404:
                logger.warning("bench: bỏ ngày %s (chưa có trong repo)", day.date())
                continue
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(resp.text, encoding="utf-8")
            paths.append(dest)
    return tuple(paths)


def normalize(line: str) -> dict[str, Any] | None:
    """Một dòng JSONL → document bench_ts. Trả về None khi bỏ dòng lỗi định dạng.

    Shape (mongodb-data-model.md §2.4): {ts, meta:{model, vendor, source, route_proto},
    status, ttft_ms, latency_ms, tps, token_count}.
    """
    try:
        row = json.loads(line)
        ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).astimezone(UTC)
        model = row["model"]
        if not isinstance(model, str) or "/" not in model:
            raise ValueError("model phải dạng provider/name")
        meta = {
            "model": model,
            "vendor": model.split("/", 1)[0],
            "source": SOURCE,
            "route_proto": row["provider"],
        }
        doc: dict[str, Any] = {"ts": ts, "meta": meta}
        for field in _TEXT_FIELDS:
            doc[field] = str(row[field])
        for field in _FLOAT_FIELDS:
            # tokens_per_sec → tps theo shape bench_ts (mongodb-data-model.md §2.4)
            doc["tps" if field == "tokens_per_sec" else field] = float(row[field])
        for field in _INT_FIELDS:
            doc[field] = int(row[field])
        return doc
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def to_docs(lines: Iterator[str]) -> list[dict[str, Any]]:
    """Chuẩn hóa + dedup theo (model, ts) + sort theo (meta, ts)."""
    seen: set[tuple[str, datetime]] = set()
    docs: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        doc = normalize(line)
        if doc is None:
            continue
        key = (doc["meta"]["model"], doc["ts"])
        if key in seen:
            continue
        seen.add(key)
        docs.append(doc)
    docs.sort(key=lambda d: (d["meta"]["model"], d["ts"]))
    return docs


def read_day(path: Path) -> Iterator[str]:
    return path.read_text(encoding="utf-8").splitlines()


async def import_bench(
    days: int,
    cache_dir: str | Path = ".cache/llm-bench-data",
    *,
    collection: AsyncCollection | None = None,
    until: datetime | None = None,
) -> int:
    """Import `days` ngày gần nhất vào collection. Trả về số document đã insert mới."""
    paths = await _fetch_files(days, cache_dir, until=until)
    docs = to_docs(
        line
        for path in paths
        for line in read_day(path)  # type: ignore[arg-type]
    )
    if collection is None or not docs:
        return 0

    # TS bucket theo meta + ts: cùng model phải liền nhau, cũ trước mới sau
    inserted = 0
    for start in range(0, len(docs), BATCH_SIZE):
        batch = docs[start : start + BATCH_SIZE]
        res = await collection.insert_many(batch, ordered=False)
        inserted += len(res.inserted_ids)
    logger.info("bench: %d docs vào %s", inserted, collection.name)
    return inserted
