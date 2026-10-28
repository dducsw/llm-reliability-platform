"""Canary prober: gửi golden prompt định kỳ 15s theo hai đường direct & via_gateway."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.events import AttemptOutcome, ProbeEvent, ProbeMeta, ProbePath, QualityResult
from reflex_mongo.collections import PROBES_TS
from reflex_telemetry import tags as t

logger = logging.getLogger(__name__)


class Prober:
    def __init__(
        self,
        db: AsyncDatabase | None = None,
        gateway_url: str = "http://localhost:8080",
        chaos_proxy_url: str = "http://localhost:8070",
        interval_s: float = 15.0,
        env: str = "local",
        seeds_path: str = "seeds/golden_prompts.yaml",
        statsd: Any | None = None,
    ) -> None:
        self.db = db
        self.gateway_url = gateway_url.rstrip("/")
        self.chaos_proxy_url = chaos_proxy_url.rstrip("/")
        self.interval_s = interval_s
        self.env = env
        self.seeds_path = Path(seeds_path)
        self._running = False
        self._prompts: list[dict[str, Any]] = []
        self.statsd = statsd

    def emit(self, event: ProbeEvent, route: str) -> None:
        """`reflex.probe.result` — nguồn cho monitor M6 (probe silence) và P_direct/P_via_gw (M9/M10)."""
        if self.statsd is None:
            return
        result = "pass" if event.quality.pass_ else "fail"
        self.statsd.increment(
            t.M_PROBE_RESULT,
            tags=[
                f"{t.ENV}:{event.meta.env}",
                f"{t.TARGET}:{event.meta.target}",
                f"{t.PATH}:{event.meta.path.value}",
                f"{t.ROUTE}:{route}",
                f"result:{result}",
            ],
        )

    def load_prompts(self) -> None:
        if self.seeds_path.exists():
            self._prompts = yaml.safe_load(self.seeds_path.read_text(encoding="utf-8")) or []
        else:
            self._prompts = [
                {
                    "id": "order.extract#1",
                    "route": "order.extract",
                    "messages": [{"role": "user", "content": "Cho mình 2 hộp khẩu trang y tế"}],
                }
            ]

    async def probe_one(
        self,
        client: httpx.AsyncClient,
        target: str,
        path: ProbePath,
        golden: dict[str, Any],
    ) -> ProbeEvent:
        now = datetime.now(tz=UTC)
        start = time.perf_counter()

        if path == ProbePath.VIA_GATEWAY:
            url = f"{self.gateway_url}/v1/chat/completions"
            headers = {"x-reflex-route": golden["route"], "x-priority": "1"}
        else:
            url = f"{self.chaos_proxy_url}/{target}/v1/chat/completions"
            headers = {"x-reflex-route": golden["route"]}

        payload = {
            "model": golden["route"],
            "messages": golden.get("messages", []),
        }

        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
            latency = (time.perf_counter() - start) * 1000.0
            status = resp.status_code

            if status == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                passed = bool(content.strip())
                outcome = AttemptOutcome.OK if passed else AttemptOutcome.QUALITY_FAIL
            else:
                passed = False
                outcome = AttemptOutcome.ERROR
        except Exception:
            latency = (time.perf_counter() - start) * 1000.0
            status = 504
            passed = False
            outcome = AttemptOutcome.TIMEOUT

        event = ProbeEvent(
            ts=now,
            meta=ProbeMeta(target=target, path=path, env=self.env),
            golden_id=golden["id"],
            outcome=outcome,
            latency_ms=latency,
            ttft_ms=latency * 0.3,
            quality=QualityResult(
                pass_=passed, checks=["not_empty"], failed=[] if passed else ["not_empty"]
            ),
            http_status=status,
        )
        return event

    async def run_once(self, targets: list[str] | None = None) -> list[ProbeEvent]:
        target_list = targets or ["vendorA:large", "vendorB:large"]
        events: list[ProbeEvent] = []

        async with httpx.AsyncClient() as client:
            for golden in self._prompts:
                for target in target_list:
                    # Bắn 2 luồng: direct và via_gateway
                    for path in (ProbePath.DIRECT, ProbePath.VIA_GATEWAY):
                        event = await self.probe_one(client, target, path, golden)
                        events.append(event)
                        self.emit(event, golden["route"])

        if self.db is not None and events:
            try:
                docs = [e.model_dump(by_alias=True) for e in events]
                await self.db[PROBES_TS].insert_many(docs, ordered=False)
            except Exception as e:
                logger.warning("Prober error inserting into %s: %s", PROBES_TS, e)

        return events

    async def run(self, targets: list[str] | None = None) -> None:
        self.load_prompts()
        self._running = True
        logger.info("Prober started with interval %.1fs", self.interval_s)

        while self._running:
            await self.run_once(targets)
            await asyncio.sleep(self.interval_s)

    def stop(self) -> None:
        self._running = False
