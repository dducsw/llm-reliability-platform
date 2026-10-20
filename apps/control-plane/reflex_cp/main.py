"""Khởi động FastAPI BFF + các module nền (sentinel, actuator, verifier, outbox) với leader lease."""

from __future__ import annotations

from fastapi import FastAPI

from reflex_cp.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    raise NotImplementedError


def run() -> None:
    raise NotImplementedError
