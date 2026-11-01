from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, utcnow
from app.database.types import JSONType, Price, UTCDateTime


class MarketScan(Base):
    """One run of the multi-timeframe orchestrator over the supported instruments, with the versions that produced it."""

    __tablename__ = "market_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)  # queued|running|completed|completed_with_errors|failed
    trigger: Mapped[str] = mapped_column(String(12), default="manual")  # manual | scheduled
    params: Mapped[dict | None] = mapped_column(JSONType)
    instruments: Mapped[list | None] = mapped_column(JSONType)  # per-instrument status, provider, coverage, reasons
    summary: Mapped[dict | None] = mapped_column(JSONType)
    config_version: Mapped[str | None] = mapped_column(String(32))
    code_version: Mapped[dict | None] = mapped_column(JSONType)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class TimeframeAnalysis(Base):
    """Independent analysis of one instrument/timeframe. Unchanged data is not re-analysed: such rows point at the earlier
    identical analysis through `reused_from_id` (same `signature` = same candles + same config)."""

    __tablename__ = "timeframe_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("market_scans.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id"))
    timeframe: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(16))  # completed | running | insufficient_data | unsupported | failed
    signature: Mapped[str | None] = mapped_column(String(64), index=True)
    reused_from_id: Mapped[int | None] = mapped_column(ForeignKey("timeframe_analyses.id"))
    n_bars: Mapped[int] = mapped_column(Integer, default=0)
    first_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    derived_from: Mapped[str | None] = mapped_column(String(4))
    result: Mapped[dict | None] = mapped_column(JSONType)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TradeOpportunity(Base):
    """The best available setup (or an explicit WAIT) for one instrument and trading style, plus any further candidates."""

    __tablename__ = "trade_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("market_scans.id", ondelete="CASCADE"), index=True)
    last_scan_id: Mapped[int] = mapped_column(ForeignKey("market_scans.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id"))
    style: Mapped[str] = mapped_column(String(12), index=True)
    direction: Mapped[str] = mapped_column(String(4))  # BUY | SELL | WAIT
    status: Mapped[str] = mapped_column(String(24), index=True)  # none|watchlist|waiting_for_confirmation|entry_triggered|invalidated|expired
    setup_timeframe: Mapped[str | None] = mapped_column(String(4))
    setup_type: Mapped[str | None] = mapped_column(String(20))
    dedupe_key: Mapped[str] = mapped_column(String(200), index=True)
    style_key: Mapped[str | None] = mapped_column(String(64))
    is_headline: Mapped[bool] = mapped_column(Boolean, default=True)
    entry_low: Mapped[Decimal | None] = mapped_column(Price)
    entry_high: Mapped[Decimal | None] = mapped_column(Price)
    stop_loss: Mapped[Decimal | None] = mapped_column(Price)
    take_profit_1: Mapped[Decimal | None] = mapped_column(Price)
    take_profit_2: Mapped[Decimal | None] = mapped_column(Price)
    take_profit_3: Mapped[Decimal | None] = mapped_column(Price)
    invalidation: Mapped[Decimal | None] = mapped_column(Price)
    risk_reward: Mapped[float | None] = mapped_column(Float)
    evidence_score: Mapped[float | None] = mapped_column(Float)
    validation_status: Mapped[str | None] = mapped_column(String(12))
    expected_holding_seconds: Mapped[int | None] = mapped_column(Integer)
    signal_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    evidence: Mapped[dict | None] = mapped_column(JSONType)  # full reasoning: MTF, structure, candles, analogues, score, risks
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class OpportunityStatusHistory(Base):
    __tablename__ = "opportunity_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("trade_opportunities.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24))
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    note: Mapped[dict | None] = mapped_column(JSONType)
