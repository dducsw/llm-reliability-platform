from reflex_cp.verifier.loop import confidently_degraded


def test_small_noisy_sample_not_degraded() -> None:
    assert not confidently_degraded(
        98, 100
    )  # 98% < 99% nhưng cận trên Wilson vẫn ≥ 99% → nhiễu mẫu


def test_clearly_bad_small_sample_degraded() -> None:
    assert confidently_degraded(9, 10)


def test_large_bad_sample_degraded() -> None:
    assert confidently_degraded(900, 1000)


def test_healthy_not_degraded() -> None:
    assert not confidently_degraded(995, 1000)
