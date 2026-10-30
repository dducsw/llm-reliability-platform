from reflex_cp.verifier.loop import confidently_degraded, plausibly_healthy


def test_small_noisy_sample_not_degraded() -> None:
    assert not confidently_degraded(
        98, 100
    )  # 98% < 99% nhưng cận trên Wilson vẫn ≥ 99% → nhiễu mẫu


def test_large_bad_sample_degraded() -> None:
    assert confidently_degraded(900, 1000)


def test_healthy_not_degraded() -> None:
    assert not confidently_degraded(995, 1000)


def test_single_failure_in_small_sample_waits_instead_of_rollback() -> None:
    # quan sát 2026-10-30: nấc 10%, ít mẫu, một lỗi → trước đây rollback
    assert not confidently_degraded(9, 10)
    assert not plausibly_healthy(9, 10)  # vùng xám → chờ


def test_clearly_bad_small_sample_rolls_back() -> None:
    assert confidently_degraded(5, 10)


def test_healthy_small_sample_advances() -> None:
    assert plausibly_healthy(10, 10)
