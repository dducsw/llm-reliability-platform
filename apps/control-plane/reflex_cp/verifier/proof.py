from __future__ import annotations

import logging
from datetime import UTC, datetime

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.actions import (
    Action,
    ActionState,
    Proportion,
    Verdict,
    VerificationResult,
)
from reflex_core.stats import two_proportion_z, wilson_interval
from reflex_mongo.collections import ACTIONS

logger = logging.getLogger(__name__)


class RecoveryVerifier:
    def __init__(self, db: AsyncDatabase | None = None) -> None:
        self.db = db

    async def verify(
        self,
        action: Action,
        baseline_good: int = 198,
        baseline_n: int = 200,
        after_good: int = 199,
        after_n: int = 200,
    ) -> VerificationResult:
        """Đo lường hồi phục qua Wilson CI và kiểm định 2 tỷ lệ (two-proportion z-test)."""
        now = datetime.now(tz=UTC)
        baseline = Proportion(good=baseline_good, n=baseline_n)
        after = Proportion(good=after_good, n=after_n)

        # 1. Tính khoảng tin cậy Wilson 95%
        after_ci = wilson_interval(after.good, after.n, confidence=0.95)

        # 2. Hai tỷ lệ z-test
        _z_score, p_val = two_proportion_z(baseline.good, baseline.n, after.good, after.n)

        # 3. Phán quyết phục hồi (Recovery Proof)
        after_rate = after.good / max(1, after.n)
        if after_rate >= 0.95 and after_ci[0] >= 0.90:
            verdict = Verdict.PASS
            action.state = ActionState.SUCCEEDED
        elif after_ci[1] < 0.85:
            verdict = Verdict.FAIL
            action.state = ActionState.FAILED
        else:
            verdict = Verdict.INCONCLUSIVE

        result = VerificationResult(
            window={
                "baseline": (now, now),
                "after": (now, now),
            },
            metric="quality",
            baseline=baseline,
            after=after,
            method="wilson+two_proportion",
            after_ci=after_ci,
            p_value=round(p_val, 4),
            verdict=verdict,
            decided_at=now,
        )

        action.verification = result
        action.updated_at = now

        if self.db is not None and action.id:
            await self.db[ACTIONS].update_one(
                {"_id": action.id},
                {
                    "$set": {
                        "state": action.state.value,
                        "verification": result.model_dump(mode="json"),
                        "updated_at": now,
                    }
                },
            )

        logger.info(
            "Verified action %s: verdict=%s (after_ci=%s, p_val=%.4f)",
            action.id or action.type,
            verdict,
            after_ci,
            p_val,
        )
        return result

    async def run(self) -> None:
        pass
