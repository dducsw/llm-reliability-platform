"""State machine incident: detected → investigating → mitigating → mitigated → resolved | false_positive."""

from __future__ import annotations

from reflex_core.incident import IncidentStatus

TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.DETECTED: {IncidentStatus.INVESTIGATING, IncidentStatus.FALSE_POSITIVE},
    IncidentStatus.INVESTIGATING: {
        IncidentStatus.MITIGATING,
        IncidentStatus.MITIGATED,
        IncidentStatus.FALSE_POSITIVE,
    },
    IncidentStatus.MITIGATING: {IncidentStatus.MITIGATED, IncidentStatus.INVESTIGATING},
    IncidentStatus.MITIGATED: {IncidentStatus.RESOLVED, IncidentStatus.INVESTIGATING},
    IncidentStatus.RESOLVED: set(),
    IncidentStatus.FALSE_POSITIVE: set(),
}


def can_transition(src: IncidentStatus, dst: IncidentStatus) -> bool:
    return dst in TRANSITIONS.get(src, set())
