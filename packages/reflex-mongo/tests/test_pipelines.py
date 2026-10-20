"""Golden tests cho A1–A18 trên fixture (atlas-local)."""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skip(reason="chưa hiện thực")]


def test_placeholder() -> None:
    ...
