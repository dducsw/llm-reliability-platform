from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    reflex_env: str = "local"
    mongodb_uri: str = ""
    mongodb_db: str = "reflex"
    gateway_url: str = "http://gateway-1:8080"
    chaos_proxy_url: str = "http://chaos-proxy:8070"
    mock_llm_url: str = "http://mock-llm:8060"
    probe_interval_s: float = 15.0
