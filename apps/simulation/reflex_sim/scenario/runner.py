"""Ghi từng phase vào chaos_runs, gửi Datadog event scenario.phase, --fast = time scale x5."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.sli import parse_window
from reflex_mongo.collections import CHAOS_RUNS
from reflex_telemetry.datadog_api import DatadogApi

from reflex_sim.chaos_proxy.runs_watcher import ChaosRunsWatcher
from reflex_sim.scenario.expectations import check as check_expectations
from reflex_sim.scenario.model import Scenario

logger = logging.getLogger(__name__)


# Cửa sổ burn của Sentinel (profile demo: 30s/180s) chạy theo giờ thật, nên không nén quá x5:
# pha lỗi phải đủ dài (≥ cửa sổ dài) thì burn rate mới vượt ngưỡng.
FAST_SCALE = 5.0


class ScenarioRunner:
    def __init__(
        self,
        db: AsyncDatabase | None = None,
        chaos_watcher: ChaosRunsWatcher | None = None,
        dd: DatadogApi | None = None,
    ) -> None:
        self.db = db
        self.chaos_watcher = chaos_watcher
        self.dd = dd

    async def _close_runs(self, run_id: str) -> None:
        if self.db is not None:
            await self.db[CHAOS_RUNS].update_many(
                {"run_id": run_id, "status": "active"},
                {"$set": {"status": "completed", "completed_at": datetime.now(tz=UTC)}},
            )

    async def run(
        self,
        scenario: Scenario,
        seed: int = 42,
        fast: bool = False,
        scale: float | None = None,
    ) -> dict[str, Any]:
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        scale = scale or (FAST_SCALE if fast else 1.0)
        start_time = time.time()
        logger.info(
            "Starting scenario %s (run_id=%s, seed=%d, fast=%s, scale=x%.0f)",
            scenario.name,
            run_id,
            seed,
            fast,
            scale,
        )

        phase_results: list[dict[str, Any]] = []

        # Monitor Datadog chỉ Alert trong lúc fault đang chạy → theo dõi song song từ đầu, không đợi hết scenario
        exps = scenario.expectations
        monitor_idx = [i for i, e in enumerate(exps) if "monitor" in e]
        total_s = sum(parse_window(p.duration) for p in scenario.phases) / scale
        monitor_task = (
            asyncio.create_task(
                check_expectations(
                    [exps[i] for i in monitor_idx],
                    start_time,
                    db=self.db,
                    scale=scale,
                    dd=self.dd,
                    monitor_watch_s=total_s,
                )
            )
            if monitor_idx
            else None
        )

        try:
            for idx, phase in enumerate(scenario.phases):
                duration_s = parse_window(phase.duration) / scale
                phase_start = datetime.now(tz=UTC)
                logger.info(
                    "Phase %d: at=%s duration=%s (scaled=%.1fs, %d faults)",
                    idx,
                    phase.at,
                    phase.duration,
                    duration_s,
                    len(phase.faults),
                )

                # Cập nhật chaos faults
                raw_faults = [f.model_dump() for f in phase.faults]
                if self.db is not None:
                    await self.db[CHAOS_RUNS].insert_one(
                        {
                            "run_id": run_id,
                            "phase_index": idx,
                            "scenario": scenario.name,
                            "faults": raw_faults,
                            "status": "active",
                            "starts_at": phase_start,
                            # Tiến trình chết giữa chừng thì fault tự hết hiệu lực (xem ChaosRunsWatcher)
                            "ends_at": phase_start + timedelta(seconds=duration_s),
                            "time_scale": scale,
                        }
                    )

                # Chờ hết thời lượng phase
                await asyncio.sleep(duration_s)
                phase_results.append(
                    {"phase": idx, "duration_s": duration_s, "faults_count": len(phase.faults)}
                )
        except BaseException:
            if monitor_task is not None:
                monitor_task.cancel()
            raise
        finally:
            # Đóng run ngay khi hết phase (không chờ expectations) hoặc khi bị huỷ/lỗi
            await self._close_runs(run_id)

        # Đánh giá expectations (monitor đã chạy song song; các loại khác kiểm tra sau khi hết phase)
        rest_idx = [i for i in range(len(exps)) if i not in monitor_idx]
        rest = await check_expectations(
            [exps[i] for i in rest_idx], start_time, db=self.db, scale=scale, dd=self.dd
        )
        monitors = await monitor_task if monitor_task is not None else []
        merged: dict[int, dict[str, Any]] = {
            **dict(zip(rest_idx, rest, strict=True)),
            **dict(zip(monitor_idx, monitors, strict=True)),
        }
        exp_results = [merged[i] for i in range(len(exps))]

        return {
            "run_id": run_id,
            "scenario": scenario.name,
            "status": "completed",
            "phases_run": len(phase_results),
            "expectations": exp_results,
            "all_passed": all(r["passed"] is not False for r in exp_results),
        }
