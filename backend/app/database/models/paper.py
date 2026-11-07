from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, utcnow
from app.database.types import JSONType, Price, UTCDateTime


class PaperAccount(Base):
    """Simulated account that applies risk rules to the signals it is offered (docs/PAPER_TRADING.md). Resetting creates a new account;
    the signal history (paper_trades) is kept."""

    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="Paper account")
    start_balance: Mapped[float] = mapped_column(Float)
    risk_pct: Mapped[float] = mapped_column(Float)  # % of the realised balance risked per trade
    max_open_positions: Mapped[int] = mapped_column(Integer)  # pending + open trades the account holds at once
    max_daily_loss_pct: Mapped[float] = mapped_column(Float)  # realised loss (% of start-of-day balance) that stops new trades for the UTC day
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PaperTrade(Base):
    """One actionable signal (EXECUTE NOW -> market order, PLACE LIMIT ORDER -> limit order) recorded when the backend first saw it, and its
    simulated outcome on later candles. Every signal is tracked (forward test of the engine); `account_taken` says whether the paper
    account's risk rules let it trade it."""

    __tablename__ = "paper_trades"
    __table_args__ = (UniqueConstraint("instrument_id", "timeframe", "setup_key", name="uq_paper_signal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("paper_accounts.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id"))
    symbol: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(4))
    setup_key: Mapped[str] = mapped_column(String(200))
    direction: Mapped[str] = mapped_column(String(4))  # BUY | SELL
    order_type: Mapped[str] = mapped_column(String(8))  # market | limit
    status: Mapped[str] = mapped_column(String(12), index=True)  # pending|open|closed|cancelled|missed|expired|skipped
    exit_reason: Mapped[str | None] = mapped_column(String(16))  # target|stop|invalidated|tp_before_fill|expired|chased|gapped
    note: Mapped[str | None] = mapped_column(String(200))
    score: Mapped[int | None] = mapped_column(Integer)
    grade: Mapped[str | None] = mapped_column(String(2))
    setup_type: Mapped[str | None] = mapped_column(String(32))
    entry_type: Mapped[str | None] = mapped_column(String(16))
    session: Mapped[str | None] = mapped_column(String(32))
    signal_ts: Mapped[datetime] = mapped_column(UTCDateTime)  # close of the candle that produced the signal
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)  # when the backend first saw it (orders start here)
    valid_until: Mapped[datetime] = mapped_column(UTCDateTime)
    entry_price: Mapped[Decimal] = mapped_column(Price)  # planned entry (the limit price for limit orders)
    stop_loss: Mapped[Decimal] = mapped_column(Price)
    take_profit: Mapped[Decimal] = mapped_column(Price)  # TP1: the exit target, as in the backtest
    invalidation: Mapped[Decimal | None] = mapped_column(Price)
    planned_rr: Mapped[float | None] = mapped_column(Float)
    fill_price: Mapped[Decimal | None] = mapped_column(Price)
    filled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    exit_price: Mapped[Decimal | None] = mapped_column(Price)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    risk: Mapped[float | None] = mapped_column(Float)  # |fill - stop| in price units
    spread: Mapped[float] = mapped_column(Float, default=0.0)  # round-trip cost in price units, charged as spread / risk R
    r_gross: Mapped[float | None] = mapped_column(Float)
    r_net: Mapped[float | None] = mapped_column(Float)
    mfe_r: Mapped[float | None] = mapped_column(Float)
    mae_r: Mapped[float | None] = mapped_column(Float)
    cursor_at: Mapped[datetime] = mapped_column(UTCDateTime)  # next candle start the simulation will process
    last_price: Mapped[float | None] = mapped_column(Float)
    last_price_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    account_taken: Mapped[bool] = mapped_column(Boolean, default=False)
    account_note: Mapped[str | None] = mapped_column(String(160))
    risk_amount: Mapped[float | None] = mapped_column(Float)  # account currency risked (fixed when the signal was recorded)
    pnl: Mapped[float | None] = mapped_column(Float)
    plan: Mapped[dict | None] = mapped_column(JSONType)  # snapshot of the plan as shown: checklist, reasons, targets
    config_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
