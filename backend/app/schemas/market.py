from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class MappingOut(BaseModel):
    provider: str
    provider_symbol: str
    exchange: str | None
    market_kind: str
    status: str
    notes: str | None


class InstrumentOut(ORM):
    id: int
    canonical_symbol: str
    name: str
    asset_class: str
    quote_currency: str
    price_precision: int
    tick_size: float | None
    calendar: str
    session_tz: str
    session_open: str
    trading_session: str | None
    meta: dict | None
    mappings: list[MappingOut] = []
    supported: bool = False


class TimeframeOut(BaseModel):
    code: str
    label: str
    seconds: int | None
    months: int | None
    native_on: list[str]


class CandleOut(BaseModel):
    time: int = Field(description="candle OPEN time, UTC epoch seconds")
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    complete: bool
    origin: str


class CandlesResponse(BaseModel):
    symbol: str
    timeframe: str
    provider: str
    price_precision: int
    count: int
    candles: list[CandleOut]


class CoverageOut(BaseModel):
    instrument: str
    provider: str
    timeframe: str
    first_ts: datetime | None
    last_ts: datetime | None
    candle_count: int
    gap_count: int
    gaps: list[dict]
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_error: str | None


class QuoteOut(BaseModel):
    symbol: str
    status: str  # ok | unsupported | not_configured | error
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    time: datetime | None = None
    provider: str | None = None
    message: str | None = None
    delayed: bool = False  # True when the price is the last known one (market closed or quote stale), never a live price


class SyncRequest(BaseModel):
    symbol: str
    timeframe: str
    bars: int = Field(default=1000, ge=10, le=100_000)
    provider: str | None = None


class ProbeRequest(BaseModel):
    symbol: str
    timeframe: str = "1H"
    provider: str | None = None
