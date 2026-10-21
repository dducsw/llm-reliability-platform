"""State machine incident: detected → investigating → mitigating → mitigated → resolved | false_positive."""

from __future__ import annotations

from reflex_core.incident import IncidentStatus

TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {}


def can_transition(src: IncidentStatus, dst: IncidentStatus) -> bool:
    raise NotImplementedError
