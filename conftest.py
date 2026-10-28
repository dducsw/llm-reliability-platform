"""Cách ly unit test khỏi `.env` của máy dev: Settings() đọc `.env`, nên token thật làm
API trả 401 trong test. Biến môi trường được ưu tiên hơn env_file → đặt rỗng ở đây;
test nào cần token thì truyền thẳng vào Settings(...)."""

import pytest

_SECRETS = ("REFLEX_CONSOLE_TOKEN", "REFLEX_WEBHOOK_TOKEN", "REFLEX_LAB_TOKEN")


@pytest.fixture(autouse=True)
def _no_dotenv_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _SECRETS:
        monkeypatch.setenv(name, "")
