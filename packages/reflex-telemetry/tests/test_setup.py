import pytest
from reflex_telemetry import setup


def test_init_returns_unified_service_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DD_TRACE_ENABLED", "false")
    monkeypatch.setenv("REFLEX_ENV", "ci")
    tel = setup.init("reflex-test")
    assert (tel.service, tel.env) == ("reflex-test", "ci")
    assert tel.version
    setup.get_logger("t").info("hello", route="order.extract")
