import pytest
from fastapi import HTTPException
from reflex_cp.api.auth import _check
from starlette.requests import Request


def _req(headers: dict[str, str] | None = None, query: str = "") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "query_string": query.encode()})


def test_empty_expected_token_allows_everything() -> None:
    _check(_req(), "")


def test_bearer_header_is_accepted() -> None:
    _check(_req({"Authorization": "Bearer s3cret"}), "s3cret")


def test_query_token_only_when_allowed() -> None:
    _check(_req(query="token=s3cret"), "s3cret", allow_query=True)
    with pytest.raises(HTTPException):
        _check(_req(query="token=s3cret"), "s3cret")


def test_wrong_token_is_rejected() -> None:
    with pytest.raises(HTTPException):
        _check(_req(query="token=nope"), "s3cret", allow_query=True)
