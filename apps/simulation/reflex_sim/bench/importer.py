"""Shallow clone → đọc data/YYYY-MM/*.jsonl → chuẩn hóa → sort (meta, ts) → insertMany batch 1000.
Dedup phía client theo (model, timestamp)."""

from __future__ import annotations


async def import_bench(days: int, cache_dir: str = ".cache/llm-bench-data") -> int:
    raise NotImplementedError
