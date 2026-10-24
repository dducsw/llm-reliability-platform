"""`reflex-mongo migrate` chạy lại nhiều lần không lỗi."""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="chưa hiện thực")]


def test_placeholder() -> None: ...
