from __future__ import annotations

from reflex_core.actions import Action, VerificationResult


class RecoveryVerifier:
    async def run(self) -> None:
        raise NotImplementedError

    async def verify(self, action: Action) -> VerificationResult:
        raise NotImplementedError
