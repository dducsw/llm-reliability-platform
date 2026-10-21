"""Hàm thuần: (policy, action) → policy mới cho từng ActionType."""

from __future__ import annotations

from reflex_core.actions import Action
from reflex_core.policy import Policy


def apply_action(policy: Policy, action: Action) -> Policy:
    raise NotImplementedError
