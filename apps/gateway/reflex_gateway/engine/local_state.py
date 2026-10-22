"""State cục bộ của gateway: breaker theo target, EWMA health/quality, inflight, retry budgets."""

from __future__ import annotations

from dataclasses import dataclass

EWMA_ALPHA = 0.1
DEFAULT_LATENCY_MS = 500.0


@dataclass(slots=True)
class _Ewma:
    value: float
    alpha: float = EWMA_ALPHA

    def update(self, sample: float) -> None:
        self.value += self.alpha * (sample - self.value)


@dataclass(slots=True)
class _TargetStats:
    health: _Ewma
    quality: _Ewma
    latency_ms: _Ewma
    inflight: int = 0


class LocalState:
    """EWMA theo (target, route). Chưa có mẫu → lạc quan (1.0) để target mới vẫn được thử."""

    def __init__(self, alpha: float = EWMA_ALPHA) -> None:
        self._alpha = alpha
        self._stats: dict[tuple[str, str], _TargetStats] = {}

    def _get(self, target: str, route: str) -> _TargetStats:
        key = (target, route)
        if key not in self._stats:
            self._stats[key] = _TargetStats(
                health=_Ewma(1.0, self._alpha),
                quality=_Ewma(1.0, self._alpha),
                latency_ms=_Ewma(DEFAULT_LATENCY_MS, self._alpha),
            )
        return self._stats[key]

    def router_inputs(self, route: str) -> dict:
        return {
            target: {"health": s.health.value, "quality": s.quality.value, "inflight": s.inflight}
            for (target, r), s in self._stats.items()
            if r == route
        }

    def on_attempt(self, target: str, route: str, ok: bool, quality_ok: bool | None) -> None:
        stats = self._get(target, route)
        stats.health.update(1.0 if ok else 0.0)
        if quality_ok is not None:
            stats.quality.update(1.0 if quality_ok else 0.0)

    def record_latency(self, target: str, route: str, latency_ms: float) -> None:
        self._get(target, route).latency_ms.update(latency_ms)

    def expected_latency_ms(self, target: str, route: str) -> float:
        return self._get(target, route).latency_ms.value

    def inflight_start(self, target: str, route: str) -> None:
        self._get(target, route).inflight += 1

    def inflight_end(self, target: str, route: str) -> None:
        stats = self._get(target, route)
        stats.inflight = max(0, stats.inflight - 1)
