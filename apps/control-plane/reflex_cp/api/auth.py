from __future__ import annotations

import hmac

from fastapi import HTTPException, Request


def _check(request: Request, expected: str) -> None:
    """Token rỗng = chưa cấu hình (dev local) → cho qua. Có token thì bắt buộc khớp."""
    if not expected:
        return
    header = request.headers.get("authorization", "")
    supplied = header[7:] if header.lower().startswith("bearer ") else ""
    supplied = supplied or request.headers.get("x-reflex-token", "")
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing token")


async def require_console_token(request: Request) -> None:
    _check(request, request.app.state.settings.reflex_console_token)


async def require_lab_token(request: Request) -> None:
    _check(request, request.app.state.settings.reflex_lab_token)
