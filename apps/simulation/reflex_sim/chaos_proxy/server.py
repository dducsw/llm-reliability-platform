from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """/{vendor}/v1/chat/completions → upstream thật hoặc mock, gắn x-chaos-fault khi có fault."""
    raise NotImplementedError
