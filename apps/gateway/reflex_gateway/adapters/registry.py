from __future__ import annotations

from reflex_gateway.adapters.base import Adapter
from reflex_gateway.adapters.mock import MockAdapter
from reflex_gateway.adapters.openai_compat import OpenaiCompatAdapter

_ADAPTERS: dict[str, Adapter] = {
    "mock": MockAdapter(),
    "openai_compat": OpenaiCompatAdapter(),
}


def get_adapter(name: str) -> Adapter:
    return _ADAPTERS.get(name, _ADAPTERS["mock"])
