"""Discrete-event simulation: clock ảo, rng seeded, gọi reflex_core.routing/breaker/retry."""

from __future__ import annotations

from reflex_cp.timemachine.world import World


def simulate(world: World, variant: str, seed: int) -> dict:
    raise NotImplementedError
