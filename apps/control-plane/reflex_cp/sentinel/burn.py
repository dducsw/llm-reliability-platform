"""A4 + A5: burn rate đa cửa sổ & budget còn lại cho mọi SLO (theo profile)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.sli import budget_remaining, burn_rate, multiwindow_fires
from reflex_mongo.collections import SLI_1M, SLOS
from reflex_mongo.pipelines import a04_burn_rate

logger = logging.getLogger(__name__)


class BurnEvaluator:
    def __init__(
        self,
        db: AsyncDatabase | None = None,
        profile: str = "demo",
        seed_slos_path: str = "seeds/slos.yaml",
    ) -> None:
        self.db = db
        self.profile = profile
        self.seed_slos_path = Path(seed_slos_path)
        # Demo profile: short=30s, long=180s, factor=14.4
        self.short_s = 30 if profile == "demo" else 300
        self.long_s = 180 if profile == "demo" else 3600
        self.factor = 14.4
        # Route lưu lượng thấp: 1 request lỗi lẻ đã đẩy burn > factor → báo động giả.
        # Chỉ kết luận khi cả hai cửa sổ có đủ mẫu.
        self.min_short = 5
        self.min_long = 20

    async def _get_slos(self) -> list[dict[str, Any]]:
        slos = []
        if self.db is not None:
            try:
                cursor = self.db[SLOS].find({})
                async for doc in cursor:
                    slos.append(doc)
            except Exception as e:
                logger.warning("Could not read slos from db: %s", e)

        if not slos and self.seed_slos_path.exists():
            try:
                slos = yaml.safe_load(self.seed_slos_path.read_text(encoding="utf-8")) or []
            except Exception as e:
                logger.warning("Could not read slos from seed: %s", e)
        return slos

    async def evaluate(self) -> list[dict[str, Any]]:
        if self.db is None:
            return []

        slos = await self._get_slos()
        now = datetime.now(tz=UTC)
        evaluations: list[dict[str, Any]] = []

        # Nhóm SLO theo scope
        by_scope: dict[str, list[dict[str, Any]]] = {}
        for slo in slos:
            scope = slo.get("scope", "route")
            by_scope.setdefault(scope, []).append(slo)

        for scope, slo_list in by_scope.items():
            keys = [s["key"] for s in slo_list if "key" in s]
            pipeline = a04_burn_rate.build(
                now=now,
                scope=scope,
                keys=keys,
                short_window_s=self.short_s,
                long_window_s=self.long_s,
            )
            try:
                rows = await (await self.db[SLI_1M].aggregate(pipeline)).to_list(None)
                row_map = {r["key"]: r for r in rows}

                for slo in slo_list:
                    key = slo.get("key")
                    objective = float(slo.get("objective", 0.99))
                    sli_type = slo.get("sli", "availability")
                    data = row_map.get(key, {})

                    if sli_type == "quality":
                        t_s = data.get("q_elig_short", 0)
                        g_s = data.get("q_good_short", 0)
                        t_l = data.get("q_elig_long", 0)
                        g_l = data.get("q_good_long", 0)
                    else:
                        t_s = data.get("t_short", 0)
                        g_s = data.get("t_short", 0) - data.get("b_short", 0)
                        t_l = data.get("t_long", 0)
                        g_l = data.get("t_long", 0) - data.get("b_long", 0)

                    b_short = burn_rate(g_s, t_s, objective) if t_s > 0 else 0.0
                    b_long = burn_rate(g_l, t_l, objective) if t_l > 0 else 0.0
                    b_rem = budget_remaining(g_l, t_l, objective) if t_l > 0 else 1.0
                    fires = (
                        t_s >= self.min_short
                        and t_l >= self.min_long
                        and multiwindow_fires(b_long, b_short, self.factor)
                    )

                    evaluations.append(
                        {
                            "slo_id": slo.get("_id", f"{scope}:{key}:{sli_type}"),
                            "scope": scope,
                            "key": key,
                            "sli": sli_type,
                            "objective": objective,
                            "burn_short": b_short,
                            "burn_long": b_long,
                            "budget_remaining": max(0.0, b_rem),
                            "factor": self.factor,
                            "fires": fires,
                            "target": slo.get("target"),
                            "route": slo.get("route", key if scope == "route" else None),
                        }
                    )
            except Exception as e:
                logger.error("Error evaluating burn rate for scope %s: %s", scope, e)

        return evaluations
