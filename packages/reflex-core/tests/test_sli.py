"""Unit tests cho reflex_core.sli."""

import pytest
from reflex_core import sli


def test_ratio() -> None:
    assert sli.ratio(10, 10) == 1.0
    assert sli.ratio(9, 10) == 0.9
    assert sli.ratio(0, 0) == 1.0


def test_burn_rate() -> None:
    # SLO 99% (budget 1%). Nếu error rate = 1%, burn rate = 1.0
    assert pytest.approx(sli.burn_rate(99, 100, 0.99)) == 1.0
    # Nếu error rate = 10% (90/100 good), burn rate = 10.0
    assert pytest.approx(sli.burn_rate(90, 100, 0.99)) == 10.0
    # Nếu không có lỗi (100/100 good), burn rate = 0.0
    assert pytest.approx(sli.burn_rate(100, 100, 0.99)) == 0.0


def test_budget_remaining() -> None:
    # 99% SLO, 99 good, 100 valid -> burn rate 1.0 -> budget remaining 0.0
    assert pytest.approx(sli.budget_remaining(99, 100, 0.99)) == 0.0
    # 100 good -> 1.0 remaining
    assert pytest.approx(sli.budget_remaining(100, 100, 0.99)) == 1.0


def test_multiwindow_fires() -> None:
    assert sli.multiwindow_fires(14.5, 15.0, 14.4) is True
    assert sli.multiwindow_fires(14.0, 15.0, 14.4) is False


def test_parse_window() -> None:
    assert sli.parse_window("30s") == 30
    assert sli.parse_window("5m") == 300
    assert sli.parse_window("1h") == 3600
    assert sli.parse_window("3d") == 259200
