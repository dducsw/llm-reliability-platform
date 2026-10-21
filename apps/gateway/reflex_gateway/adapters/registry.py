from __future__ import annotations

from reflex_gateway.adapters.base import Adapter


def get_adapter(name: str) -> Adapter:
    raise NotImplementedError
