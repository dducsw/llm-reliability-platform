from pathlib import Path

import pytest
from reflex_core.policy import Candidate, CandidateRole, Policy
from reflex_gateway.policy_store import PolicyStore

SEED = """
- _id: chat.reply
  version: 3
  candidates:
    - { target: "mock:large", weight: 1.0, role: primary }
"""


@pytest.mark.asyncio
async def test_loads_seed_file_when_no_db(tmp_path: Path) -> None:
    seed = tmp_path / "policies.yaml"
    seed.write_text(SEED)
    store = PolicyStore(db=None, seed_file=str(seed))
    assert not store.ready
    await store.start()
    assert store.ready
    policy = store.get("chat.reply")
    assert policy is not None and policy.version == 3
    assert store.get("unknown") is None


def test_set_replaces_policy_by_route() -> None:
    store = PolicyStore(db=None)
    cand = [Candidate(target="mock:large", weight=1.0, role=CandidateRole.PRIMARY)]
    store.set(Policy(_id="r", version=1, candidates=cand))
    store.set(Policy(_id="r", version=2, candidates=cand))
    assert store.get("r").version == 2  # type: ignore[union-attr]
