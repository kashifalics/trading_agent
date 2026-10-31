from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.backtesting.strategies import STRATEGIES
from app.market_data.timeframes import TIMEFRAMES
from app.schemas.common import ORM


class BacktestRunRequest(BaseModel):
    symbol: str
    timeframe: str
    provider: str | None = None
    strategy: str = "decision_engine"
    bars: int = Field(default=3000, ge=300, le=50_000)
    start: datetime | None = None
    end: datetime | None = None
    initial_equity: float = Field(default=10_000, gt=0)
    risk_pct: float = Field(default=1.0, gt=0, le=10)
    spread: float = Field(default=0.0, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    commission_pct: float = Field(default=0.0, ge=0, le=5)
    max_bars_in_trade: int = Field(default=200, ge=1, le=5000)
    eval_every: int = Field(default=2, ge=1, le=100)
    allowed_hours_utc: list[int] | None = None
    auto_sync: bool = True

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("timeframe")
    @classmethod
    def _tf(cls, v: str) -> str:
        if v not in TIMEFRAMES:
            raise ValueError("unsupported timeframe")
        return v

    @field_validator("strategy")
    @classmethod
    def _strategy(cls, v: str) -> str:
        if v not in STRATEGIES:
            raise ValueError(f"unknown strategy; use one of {list(STRATEGIES)}")
        return v


class BacktestTradeOut(ORM):
    direction: str
    signal_ts: datetime
    entry_ts: datetime
    entry_price: float
    exit_ts: datetime
    exit_price: float
    exit_reason: str
    stop_loss: float
    take_profit: float | None
    units: float
    pnl: float
    r_multiple: float
    costs: float


class BacktestOut(ORM):
    id: int
    instrument_id: int
    symbol: str | None = None
    timeframe: str
    strategy: str
    status: str
    config: dict | None
    metrics: dict | None
    equity_curve: list | None
    start_ts: datetime | None
    end_ts: datetime | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    trades: list[BacktestTradeOut] = []
