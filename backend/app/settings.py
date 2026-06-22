"""
Application settings (pydantic-settings).

Replaces the original ``src/config.py`` which exited the process on import.
Nothing here has import-time side effects; values come from environment
variables and an optional ``.env`` file.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Environment -------------------------------------------------------
    app_env: str = "dev"
    engine_version: str = "0.1.0"

    # --- Database (one URL selects the backend) ---------------------------
    # Docker:    postgresql+asyncpg://user:pass@postgres:5432/rubric
    # No-Docker: sqlite+aiosqlite:///./data/app.db
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    auto_migrate: bool = True  # run alembic upgrade head on startup (no-Docker convenience)

    # --- Worker / jobs -----------------------------------------------------
    embedded_worker: bool = True   # run the worker in-process (no-Docker single command)
    worker_concurrency: int = 2
    worker_poll_interval: float = 0.5
    job_lease_seconds: int = 300
    job_max_attempts: int = 3

    # --- LLM ---------------------------------------------------------------
    llm_backend: str = "litellm"           # "litellm" | "fake"
    default_model: str = "openrouter/openai/gpt-oss-120b:free"
    openrouter_api_key: str | None = None  # BYOK default (also configurable in-app)
    llm_concurrency: int = 1               # keep at 1 for free, rate-limited models
    llm_call_timeout: float = 60.0
    llm_max_attempts: int = 4
    llm_temperature: float = 0.0
    review_deadline_seconds: int = 600
    grading_mode: str = "per_criterion"    # "per_criterion" | "batched"

    # --- Ingestion caps ----------------------------------------------------
    max_total_mb: int = 10
    max_file_count: int = 5000
    max_file_bytes: int = 1024 * 1024  # 1 MB per file
    blob_dir: str = "./data/blobs"
    clone_timeout: int = 120

    # --- Security ----------------------------------------------------------
    operator_token: str = "dev-operator-token"  # CHANGE in production
    app_secret_key: str = "dev-insecure-secret-change-me"  # derives the Fernet key

    # --- CORS --------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Optional Telegram notifications (thin client of this API) ---------
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    web_base_url: str = "http://localhost:3000"

    @property
    def sync_database_url(self) -> str:
        """A synchronous SQLAlchemy URL for tooling that needs one."""
        url = self.database_url
        if url.startswith("sqlite+aiosqlite"):
            return url.replace("sqlite+aiosqlite", "sqlite", 1)
        if url.startswith("postgresql+asyncpg"):
            return url.replace("postgresql+asyncpg", "postgresql+psycopg", 1)
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
