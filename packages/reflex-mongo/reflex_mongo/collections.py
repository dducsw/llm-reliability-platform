"""Tên collection + cấu hình Time Series / TTL (mongodb-data-model.md §1–§5)."""

from __future__ import annotations

from typing import Final

# Hot — Time Series
REQUESTS_TS: Final = "requests_ts"
ATTEMPTS_TS: Final = "attempts_ts"
PROBES_TS: Final = "probes_ts"
BENCH_TS: Final = "bench_ts"

# Warm — rollup
SLI_1M: Final = "sli_1m"
SLI_1H: Final = "sli_1h"
BASELINES: Final = "baselines"

# Operational (một số được watch bằng Change Streams)
TARGETS: Final = "targets"
SLOS: Final = "slos"
POLICIES: Final = "policies"  # watched
POLICY_HISTORY: Final = "policy_history"
HEALTH_STATE: Final = "health_state"  # watched
INCIDENTS: Final = "incidents"  # watched
INVESTIGATIONS: Final = "investigations"
ACTIONS: Final = "actions"  # watched
POSTMORTEMS: Final = "postmortems"
REPLAYS: Final = "replays"
CHAOS_RUNS: Final = "chaos_runs"  # watched
OUTBOX: Final = "outbox"
STREAM_CHECKPOINTS: Final = "stream_checkpoints"
LEASES: Final = "leases"

DAY_S: Final = 86_400

TIMESERIES: Final[dict[str, dict[str, object]]] = {
    REQUESTS_TS: {"granularity": "seconds", "ttl_s": 14 * DAY_S},
    ATTEMPTS_TS: {"granularity": "seconds", "ttl_s": 14 * DAY_S},
    PROBES_TS: {"granularity": "seconds", "ttl_s": 14 * DAY_S},
    BENCH_TS: {"granularity": "hours", "ttl_s": None},
}

TTL: Final[dict[str, int]] = {
    SLI_1M: 45 * DAY_S,
    SLI_1H: 400 * DAY_S,
}

WATCHED: Final = (POLICIES, HEALTH_STATE, INCIDENTS, ACTIONS, CHAOS_RUNS)
