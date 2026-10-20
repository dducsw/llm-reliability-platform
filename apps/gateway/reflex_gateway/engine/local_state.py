"""State cục bộ của gateway: breaker theo target, EWMA health/quality, inflight, retry budgets."""

from __future__ import annotations


class LocalState:
    def router_inputs(self, route: str) -> dict:
        raise NotImplementedError

    def on_attempt(self, target: str, route: str, ok: bool, quality_ok: bool | None) -> None:
        raise NotImplementedError
