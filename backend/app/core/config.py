from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-env"


class Settings(BaseSettings):
    # Later files win: backend/.env overrides the project-root .env (which docker compose and scripts/setup also use).
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "development"
    app_secret_key: str = Field(_DEFAULT_SECRET, repr=False)
    database_url: str = Field("sqlite:///./dev.db", repr=False)
    migration_database_url: str | None = Field(None, repr=False)
    redis_url: str | None = Field(None, repr=False)
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    binance_api_base_url: str = "https://api.binance.com"
    twelve_data_api_key: str | None = Field(None, repr=False)
    twelve_data_base_url: str = "https://api.twelvedata.com"

    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = Field(None, repr=False)
    s3_secret_key: str | None = Field(None, repr=False)
    s3_region: str | None = None

    llm_provider: str = "none"
    llm_model: str | None = None
    openai_api_key: str | None = Field(None, repr=False)
    sentry_dsn: str | None = Field(None, repr=False)

    auth_required: bool = False
    rate_limit_per_minute: int = 240
    job_backend: str = "inline"  # inline | celery
    auto_migrate: bool = True
    model_dir: str = "./model_store"
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 8_000_000

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _driver(cls, v: str | None) -> str | None:
        """Managed Postgres hosts hand out `postgres://` / `postgresql://`; SQLAlchemy needs the psycopg 3 dialect."""
        if v and v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v and v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate_for_runtime(self) -> None:
        if self.is_production and self.app_secret_key == _DEFAULT_SECRET:
            raise RuntimeError("APP_SECRET_KEY must be set in production")
        if self.is_production and not self.auth_required:
            raise RuntimeError("AUTH_REQUIRED must be true in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
