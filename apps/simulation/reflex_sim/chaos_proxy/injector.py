"""Áp fault lên response (non-stream) hoặc stream chunks."""

from __future__ import annotations

import random

from reflex_sim.chaos_proxy.faults import Fault


def select(faults: list[Fault], target: str, route: str | None, rng: random.Random) -> list[Fault]:
    raise NotImplementedError


def apply(fault: Fault, response: dict, rng: random.Random) -> dict:
    raise NotImplementedError
