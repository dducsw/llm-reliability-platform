from __future__ import annotations

from fastapi import Request


async def require_console_token(request: Request) -> None:
    raise NotImplementedError


async def require_lab_token(request: Request) -> None:
    raise NotImplementedError
