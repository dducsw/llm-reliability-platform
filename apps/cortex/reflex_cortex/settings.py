from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    reflex_env: str = "local"
    mongodb_uri: str = ""
    mongodb_db: str = "reflex"
    gateway_url: str = "http://gateway-1:8080"
    reason_route: str = "cortex.reason"
    max_tool_calls: int = 12
    max_wall_s: int = 90
    auto_confidence: float = 0.7
    dd_api_key: str = ""
    dd_app_key: str = ""
    dd_site: str = ""
