"""Explain tests cho MongoDB Aggregation Pipelines (DE-1.5).

Quy t?c ki?m tra:
1. Trn collection thu?ng: tuy?t d?i khng c COLLSCAN (ph?i dng IXSCAN).
2. Trn Time Series (attempts_ts, requests_ts): b?t bu?c c bucket filter trn `meta` v `control.min/max.ts`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pymongo.asynchronous.database import AsyncDatabase
from reflex_mongo.collections import ATTEMPTS_TS, SLI_1M
from reflex_mongo.pipelines import (
    a01_attempt_rollup,
    a04_burn_rate,
)

pytestmark = pytest.mark.integration


def _has_collscan(stage: dict[str, Any] | list[Any]) -> bool:
    """Qut d? quy cy executionStats t?m stage COLLSCAN."""
    if isinstance(stage, list):
        return any(_has_collscan(item) for item in stage)
    if not isinstance(stage, dict):
        return False

    if stage.get("stage") == "COLLSCAN":
        return True

    for _k, v in stage.items():
        if isinstance(v, (dict, list)) and _has_collscan(v):
            return True
    return False


def assert_no_collscan(explain_result: dict[str, Any]) -> None:
    """Kh?ng d?nh pipeline dng index, khng qut toan b? b?ng (COLLSCAN)."""
    stages = explain_result.get("stages", [])
    exec_stats = explain_result.get("executionStats", {})
    query_planner = explain_result.get("queryPlanner", {})

    assert not _has_collscan(stages), f"Pht hi?n COLLSCAN trong pipeline stages: {stages}"
    assert not _has_collscan(exec_stats), f"Pht hi?n COLLSCAN trong executionStats: {exec_stats}"
    assert not _has_collscan(query_planner), (
        f"Pht hi?n COLLSCAN trong queryPlanner: {query_planner}"
    )


@pytest.mark.asyncio
async def test_a01_explain_has_bucket_skip(it_db: AsyncDatabase[dict[str, Any]]) -> None:
    """A1 Attempt rollup trn Time Series: c b? l?c th?i gian d? bucket filter."""
    now = datetime.now(tz=UTC)
    pipeline = a01_attempt_rollup.build(
        from_time=now - timedelta(minutes=5), to_time=now, env="local"
    )

    explain = await it_db[ATTEMPTS_TS].aggregate(pipeline).explain()
    assert explain is not None


@pytest.mark.asyncio
async def test_a04_burn_rate_explain(it_db: AsyncDatabase[dict[str, Any]]) -> None:
    """A4 Burn rate: explain trn sli_1m."""
    now = datetime.now(tz=UTC)
    pipeline = a04_burn_rate.build(now=now, scope="target", keys=["vendorA:large"])

    explain = await it_db[SLI_1M].aggregate(pipeline).explain()
    assert explain is not None
    assert_no_collscan(explain)
