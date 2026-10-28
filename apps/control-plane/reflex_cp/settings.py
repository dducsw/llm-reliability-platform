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
    # Watchdog R4 (Cortex chết): 0 = theo profile (demo 15s/120s, standard 60s/180s)
    cortex_unclaimed_s: float = 0.0
    cortex_stale_s: float = 0.0
    cortex_watchdog_enabled: bool = True
    reflex_webhook_token: str = ""
    reflex_console_token: str = ""
    reflex_lab_token: str = ""
    dd_api_key: str = ""
    dd_app_key: str = ""
    dd_site: str = "datadoghq.com"

    def watchdog_thresholds(self) -> tuple[float, float]:
        demo = self.reflex_profile == "demo"
        unclaimed = self.cortex_unclaimed_s or (15.0 if demo else 60.0)
        # > max_wall_s (90s) của Cortex để không cướp một investigation còn đang chạy
        stale = self.cortex_stale_s or (120.0 if demo else 180.0)
        return unclaimed, stale
