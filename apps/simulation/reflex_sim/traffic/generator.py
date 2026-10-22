"""ShopMate Traffic Generator: sinh tải đa route với nhịp ngày đêm."""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid

import httpx
from reflex_sim.traffic.diurnal import rate_at
from reflex_sim.traffic.prompts import make_prompt

logger = logging.getLogger(__name__)


class TrafficGenerator:
    def __init__(
        self,
        gateway_url: str = "http://localhost:8080",
        base_rps: float = 8.0,
        mix: dict[str, float] | None = None,
        amplitude: float = 0.3,
        period_s: float = 600.0,
        seed: int = 42,
    ) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.base_rps = base_rps
        self.mix = mix or {"chat.reply": 0.5, "order.extract": 0.35, "support.triage": 0.15}
        self.amplitude = amplitude
        self.period_s = period_s
        self.rng = random.Random(seed)
        self._running = False

    def _pick_route(self) -> str:
        routes = list(self.mix.keys())
        weights = list(self.mix.values())
        return self.rng.choices(routes, weights=weights, k=1)[0]

    async def send_one(self, client: httpx.AsyncClient, t_start: float) -> int:
        route = self._pick_route()
        messages = make_prompt(route, self.rng)
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        priority = self.rng.choices([1, 2, 3], weights=[0.7, 0.2, 0.1], k=1)[0]

        headers = {
            "x-reflex-route": route,
            "x-reflex-session": session_id,
            "x-priority": str(priority),
        }
        payload = {
            "model": route,
            "messages": messages,
        }

        try:
            resp = await client.post(
                f"{self.gateway_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            return resp.status_code
        except Exception as e:
            logger.debug("TrafficGenerator request failed: %s", e)
            return 500

    async def run(self, duration_s: float | None = None) -> None:
        self._running = True
        start_time = time.time()
        sent = 0

        async with httpx.AsyncClient() as client:
            while self._running:
                now = time.time()
                elapsed = now - start_time
                if duration_s is not None and elapsed >= duration_s:
                    break

                current_rps = rate_at(elapsed, self.base_rps, self.amplitude, self.period_s)
                delay = 1.0 / current_rps

                asyncio.create_task(self.send_one(client, elapsed))
                sent += 1
                await asyncio.sleep(delay)

        logger.info(
            "TrafficGenerator finished: %d requests sent in %.1fs", sent, time.time() - start_time
        )

    def stop(self) -> None:
        self._running = False
