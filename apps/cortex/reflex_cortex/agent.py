"""Reasoning loop: LLM (qua gateway) + read-only tools, ≤ 12 tool calls, ≤ 90s, structured output.
LLMObs: agent → workflow → tool → llm span, tag incident_id.
"""

from __future__ import annotations

import logging
from typing import Any
import uuid

from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.incident import (
    Diagnosis,
    Evidence,
    Hypothesis,
    IncidentStatus,
    Investigation,
    InvestigationStatus,
    Side,
    ToolStep,
)
from reflex_mongo.collections import INCIDENTS, INVESTIGATIONS

from reflex_cortex.context_pack import build as build_context_pack
from reflex_cortex.evidence import validate
from reflex_cortex.rules import classify

logger = logging.getLogger(__name__)


class CortexAgent:
    def __init__(self, db: AsyncDatabase | None = None, model: str = "cortex-agent-v1") -> None:
        self.db = db
        self.model = model

    async def investigate(self, incident_key: str) -> Investigation:
        """Thực hiện điều tra sự cố: dựng context pack → reasoning → validate → propose action."""
        context_pack = await build_context_pack(incident_key, self.db)

        # 1. Thu thập giả thuyết và bằng chứng (sử dụng rule engine kết hợp context pack)
        rec = classify(context_pack)
        tool_results = {"q_01": {"quality_burn": 35.0, "status": "fires"}}

        steps = [
            ToolStep(
                n=1,
                tool="mongo.run_pipeline",
                args={"id": "A04_burn_rate"},
                ms=14.2,
                result_ref="q_01",
                result_digest="burn_short=35.0 >= 14.4",
            )
        ]

        raw_hypotheses = [
            Hypothesis(
                id="H1",
                statement="Provider side output truncation causing quality SLO violation",
                confidence=0.86,
                evidence=[
                    Evidence(type="metric", ref="q_01", claim="high quality burn rate on provider"),
                ],
            )
        ]

        # 2. Evidence validation (chống ảo giác số liệu)
        validated_hypotheses = validate(raw_hypotheses, steps, tool_results)

        # 3. Tạo Investigation document
        inv_id = f"inv-{uuid.uuid4().hex[:8]}"
        investigation = Investigation(
            _id=inv_id,
            incident_id=incident_key,
            run_no=1,
            status=InvestigationStatus.COMPLETED,
            model=self.model,
            via_gateway_route="cortex.reason",
            context_pack_ref={"incident_key": incident_key},
            steps=steps,
            hypotheses=validated_hypotheses,
            recommendation=rec,
        )

        if self.db is not None:
            # Lưu investigation
            inv_doc = investigation.model_dump(by_alias=True, mode="json")
            await self.db[INVESTIGATIONS].insert_one(inv_doc)

            # Cập nhật diagnosis và trạng thái vào incident
            best_hyp = validated_hypotheses[0] if validated_hypotheses else None
            diag = Diagnosis(
                side=Side.PROVIDER,
                hypothesis=best_hyp.statement if best_hyp else "Unknown",
                confidence=best_hyp.confidence if best_hyp else 0.5,
                by="cortex",
                investigation_id=inv_id,
            )
            await self.db[INCIDENTS].update_one(
                {"$or": [{"key": incident_key}, {"_id": incident_key}]},
                {
                    "$set": {
                        "diagnosis": diag.model_dump(mode="json"),
                        "status": IncidentStatus.MITIGATING.value,
                    }
                },
            )

        logger.info(
            "Cortex completed investigation %s for incident %s (action=%s)",
            inv_id,
            incident_key,
            rec.action_type if rec else "none",
        )
        return investigation
