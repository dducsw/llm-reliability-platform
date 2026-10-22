"""Unit tests cho reflex_core.stats."""

from reflex_core import stats


def test_wilson_interval() -> None:
    # 98/100 -> around 0.98, lower ~0.93, upper ~0.99
    low, high = stats.wilson_interval(98, 100, 0.95)
    assert 0.92 < low < 0.96
    assert 0.98 < high < 1.0
    assert low < high


def test_wilson_interval_bounds() -> None:
    low, high = stats.wilson_interval(0, 10)
    assert low == 0.0
    assert high < 0.35

    low, high = stats.wilson_interval(10, 10)
    assert low > 0.65
    assert high == 1.0


def test_two_proportion_z() -> None:
    # a: 70/100 (0.70), b: 95/100 (0.95) -> b rõ ràng tốt hơn a
    z, p_val = stats.two_proportion_z(70, 100, 95, 100)
    assert z > 3.0
    assert p_val < 0.01  # cực kỳ có ý nghĩa thống kê

    # a: 95/100, b: 70/100 -> b kém hơn a -> p_val gần 1.0 (one-sided H1: b > a)
    z_rev, p_val_rev = stats.two_proportion_z(95, 100, 70, 100)
    assert z_rev < -3.0
    assert p_val_rev > 0.99


def test_min_samples() -> None:
    assert stats.min_samples(0.99) == 200
