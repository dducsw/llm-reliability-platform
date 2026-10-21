"""FastAPI app factory, lifespan (policy store, health sync, telemetry writer), ddtrace init."""

from __future__ import annotations

from fastapi import FastAPI

from reflex_gateway.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    raise NotImplementedError


def run() -> None:
    """Entry point `reflex-gateway` (uvicorn)."""
    raise NotImplementedError
