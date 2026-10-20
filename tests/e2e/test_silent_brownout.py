"""S1 e2e (testing-strategy.md): incident ≤ 60s, delivered quality ≥ 99%, shift_weight PASS,
resolved sau failback, Memory +1."""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.skip(reason="chưa hiện thực")]


def test_placeholder() -> None:
    ...
