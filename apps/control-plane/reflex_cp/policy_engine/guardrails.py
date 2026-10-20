"""Guardrails: schema, single_flight, cooldown, flap_guard, healthy_destination, capacity,
cost_ceiling, blast_radius, confidence, human_only (recovery-engine.md §4)."""

from __future__ import annotations

from reflex_core.actions import Action, GuardrailResult


async def evaluate_all(action: Action) -> list[GuardrailResult]:
    raise NotImplementedError
