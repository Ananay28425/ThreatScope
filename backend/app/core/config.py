from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ────────────────────────────────────────────────────────────
    app_name: str = "ThreatScope"
    app_env: str = "development"
    secret_key: str = "changeme"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://threatscope:threatscope@postgres:5432/threatscope"
    sync_database_url: str = "postgresql://threatscope:threatscope@postgres:5432/threatscope"

    # ── Valkey ────────────────────────────────────────────────────────────────
    # Valkey is a FOSS (BSD-3-Clause) drop-in replacement for Redis.
    # redis-py uses the same RESP protocol, so this just works.
    valkey_url: str = "redis://valkey:6379/0"

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://valkey:6379/1"
    celery_result_backend: str = "redis://valkey:6379/2"

    # ── Correlation Engine ────────────────────────────────────────────────────
    correlation_window_seconds: int = 120
    alert_threshold_nodes: int = 3
    alert_threshold_score: float = 0.80

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = 60

    # ── Prometheus ────────────────────────────────────────────────────────────
    metrics_port: int = 9100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
