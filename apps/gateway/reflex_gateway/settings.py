from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    reflex_env: str = "local"
    gateway_id: str = "gw-1"
    host: str = "0.0.0.0"
    port: int = 8080
    mongodb_uri: str = ""
    mongodb_db: str = "reflex"
    policy_snapshot_path: str = "/tmp/reflex-policies.json"
    telemetry_queue_max: int = 10_000
    telemetry_batch_size: int = 500
    telemetry_flush_ms: int = 250
    health_sync_interval_s: float = 10.0
