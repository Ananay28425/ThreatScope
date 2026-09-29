"""Validated runtime configuration; production cannot fall back to development secrets."""
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://threatscope@localhost/threatscope"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cookie_secure: bool = False
    session_hours: int = Field(default=8, ge=1, le=24)
    window_seconds: int = Field(default=120, ge=10, le=600)
    quorum: int = Field(default=3, ge=2, le=20)
    score_threshold: float = Field(default=0.80, ge=0, le=1)
    request_timeout_seconds: int = Field(default=90, ge=5, le=600)
    ingest_per_minute: int = Field(default=120, ge=1, le=10000)
    login_per_minute: int = Field(default=10, ge=1, le=100)
    max_body_bytes: int = 16384
    llm_url: str = "http://127.0.0.1:8080/v1"
    llm_api_key: str = ""
    llm_model: str = "Qwen3-1.7B-Q4_K_M"
    llm_enabled: bool = False
    llm_timeout_seconds: int = Field(default=45, ge=1, le=120)
    llm_ca_file: str | None = None
    worker_poll_seconds: float = Field(default=0.25, ge=0.05, le=10)

    @property
    def origins(self) -> set[str]:
        return {s.strip() for s in self.allowed_origins.split(",") if s.strip()}

    @model_validator(mode="after")
    def validate_boundaries(self):
        if self.database_url.startswith("sqlite") and self.app_env != "test":
            raise ValueError("sqlite_coordinator_is_test_only")
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("production_requires_secure_cookie")
        parsed = urlparse(self.llm_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("llm_url_must_not_contain_credentials_or_query")
        if self.llm_enabled and parsed.hostname not in {"localhost", "127.0.0.1", "::1", "llm"}:
            if parsed.scheme != "https" or not self.llm_api_key:
                raise ValueError("remote_inference_requires_tls_and_api_key")
        if "*" in self.origins:
            raise ValueError("explicit_origins_required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
