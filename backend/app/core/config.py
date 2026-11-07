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
    oanda_api_token: str | None = Field(None, repr=False)
    oanda_base_url: str = "https://api-fxpractice.oanda.com"  # practice (demo) environment
    biquote_base_url: str = "https://biquote.io"  # free public API, no key (docs/BIQUOTE_PROVIDER_EVALUATION.md)
    # Provider used when a request does not name one, for every instrument that has a (non-unsupported) mapping to it. Empty = pick by mapping status
    # (Binance for BTCUSDT, Twelve Data for XAUUSD, OANDA for US30/USOIL). Explicit `provider=` always wins; the other providers stay registered.
    preferred_provider: str = "biquote"

    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = Field(None, repr=False)
    s3_secret_key: str | None = Field(None, repr=False)
    s3_region: str | None = None

    llm_provider: str = "none"
    llm_model: str | None = None
    openai_api_key: str | None = Field(None, repr=False)
    sentry_dsn: str | None = Field(None, repr=False)

    # Instruments shown by default in the UI/API (comma separated). Others stay registered and reachable with ?all=true.
    focus_symbols: str = "BTCUSDT,XAUUSD"
    auth_required: bool = False
    rate_limit_per_minute: int = 240
    job_backend: str = "inline"  # inline | celery
    auto_migrate: bool = True

    # Trade Opportunities module (docs/TRADE_OPPORTUNITIES_ARCHITECTURE.md)
    opportunity_symbols: str = "XAUUSD,US30,BTCUSDT,USOIL"
    opportunity_scan_interval_minutes: int = 0  # 0 = automatic scanning disabled (manual / API-triggered only)
    opportunity_refresh_providers: str = "biquote,binance"  # providers the SCHEDULED scan may sync (quota-limited providers stay manual)
    opportunity_max_sync_tfs: int = 4  # timeframes refreshed per instrument when a scan is asked to refresh data

    # Signal engine (docs/SIGNAL_ENGINE.md)
    signal_symbols: str = "XAUUSD,BTCUSDT,US30,USOIL"
    signal_spreads: str = "BTCUSDT:2,XAUUSD:0.30"  # round-trip spread in PRICE units per instrument (your broker's typical spread)
    # instrument:provider used by the signal engine (one provider per instrument, never mixed). Binance gives BTCUSDT deep history keyless.
    signal_provider_overrides: str = "BTCUSDT:binance"
    signal_refresh_providers: str = "biquote,binance"  # providers the Signals page may sync (quota-limited providers stay manual)

    # Paper trading (docs/PAPER_TRADING.md): simulated orders only, no broker connectivity
    paper_trading_interval_seconds: int = 60  # in-process cycle (sync -> analyse -> record -> simulate); 0 = off (run via the API only)
    paper_start_balance: float = 10_000.0  # defaults for a new paper account (editable from the Paper Trading page)
    paper_risk_pct: float = 0.5
    paper_max_open_positions: int = 5
    paper_max_daily_loss_pct: float = 2.0
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
    def focus_list(self) -> set[str]:
        return {s.strip().upper() for s in self.focus_symbols.split(",") if s.strip()}

    @property
    def opportunity_list(self) -> list[str]:
        return [s.strip().upper() for s in self.opportunity_symbols.split(",") if s.strip()]

    @property
    def signal_list(self) -> list[str]:
        return [s.strip().upper() for s in self.signal_symbols.split(",") if s.strip()]

    @property
    def signal_refresh_list(self) -> list[str]:
        return [s.strip().lower() for s in self.signal_refresh_providers.split(",") if s.strip()]

    @property
    def opportunity_refresh_list(self) -> list[str]:
        return [s.strip().lower() for s in self.opportunity_refresh_providers.split(",") if s.strip()]

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
