from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    reflex_env: str = "local"
    reflex_profile: str = "demo"  # demo | standard
    instance_id: str = "cp-1"
    host: str = "0.0.0.0"
    port: int = 8090
    mongodb_uri: str = ""
    mongodb_db: str = "reflex"
    sentinel_tick_s: float = 10.0
    reflex_webhook_token: str = ""
    reflex_console_token: str = ""
    reflex_lab_token: str = ""
