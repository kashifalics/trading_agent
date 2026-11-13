from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, utcnow
from app.database.types import JSONType, UTCDateTime


class SignalRecord(Base):
    """A strategy-engine v2 signal and its lifecycle (DETECTED -> WAITING FOR ENTRY / ENTRY READY -> ENTRY TRIGGERED -> ACTIVE ->
    TP1/TP2/TP3 HIT | STOP LOSS HIT | INVALIDATED | EXPIRED | ENTRY MISSED), updated from 1-minute candles. Hypothetical signal
    tracking only: never a paper trade, never an order (docs/engine_v2/DESIGN.md section 9)."""

    __tablename__ = "signal_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_key: Mapped[str] = mapped_column(String(160), unique=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id"))
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(4))
    strategy: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(4))  # BUY | SELL
    regime: Mapped[str | None] = mapped_column(String(20))
    entry_mode: Mapped[str] = mapped_column(String(8))  # market | limit | stop
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float | None] = mapped_column(Float)
    tp3: Mapped[float | None] = mapped_column(Float)
    invalidation: Mapped[float] = mapped_column(Float)
    risk: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), index=True)
    research_status: Mapped[str] = mapped_column(String(24))
    signal_time: Mapped[datetime] = mapped_column(UTCDateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(timezone=True))
    triggered_at: Mapped[datetime | None] = mapped_column(UTCDateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(timezone=True))
    cursor_at: Mapped[datetime | None] = mapped_column(UTCDateTime(timezone=True))  # last 1-minute candle processed
    last_price: Mapped[float | None] = mapped_column(Float)
    best_target: Mapped[int] = mapped_column(Integer, default=0)  # highest TP reached (0-3)
    history: Mapped[list] = mapped_column(JSONType, default=list)  # [{status, at, price, note}]
    plan: Mapped[dict] = mapped_column(JSONType, default=dict)  # the full plan as shown when detected
    engine_version: Mapped[str] = mapped_column(String(32))
