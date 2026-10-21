"""Unit/property tests cho reflex_core.hist."""

import pytest
from reflex_core import hist


def test_empty_hist() -> None:
    h = hist.empty()
    assert len(h) == hist.NB
    assert all(x == 0 for x in h)


def test_bucket_index_bounds() -> None:
    assert hist.bucket_index(10) == 0  # <= 50
    assert hist.bucket_index(50) == 0
    assert hist.bucket_index(50.1) == 1
    assert hist.bucket_index(100) == 1
    assert hist.bucket_index(32000) == 18
    assert hist.bucket_index(35000) == 19


def test_observe_and_merge() -> None:
    h1 = hist.empty()
    hist.observe(h1, 40)
    hist.observe(h1, 150)

    h2 = hist.empty()
    hist.observe(h2, 150)
    hist.observe(h2, 35000)

    merged = hist.merge(h1, h2)
    assert merged[0] == 1  # 40 ms
    assert merged[2] == 2  # 150 ms (bucket 2 is (100, 150])
    assert merged[19] == 1  # 35000 ms


def test_count_le() -> None:
    h = hist.empty()
    hist.observe(h, 40)  # bucket 0 (<= 50)
    hist.observe(h, 90)  # bucket 1 (50, 100]
    hist.observe(h, 250)  # bucket 3 (200, 300]

    assert hist.count_le(h, 50) == 1
    assert hist.count_le(h, 100) == 2
    assert hist.count_le(h, 200) == 2
    assert hist.count_le(h, 300) == 3


def test_quantile_interpolation() -> None:
    h = hist.empty()
    # 100 quan sát từ 0 đến 50ms
    for _ in range(100):
        hist.observe(h, 25)

    p50 = hist.quantile(h, 0.5)
    assert pytest.approx(p50, abs=1.0) == 25.0

    p90 = hist.quantile(h, 0.9)
    assert pytest.approx(p90, abs=1.0) == 45.0
