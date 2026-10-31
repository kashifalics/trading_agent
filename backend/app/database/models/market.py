from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.database.types import BigIntPK, JSONType, Price, UTCDateTime


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_symbol: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    asset_class: Mapped[str] = mapped_column(String(32))
    quote_currency: Mapped[str] = mapped_column(String(16))
    price_precision: Mapped[int] = mapped_column(Integer)
    tick_size: Mapped[Decimal | None] = mapped_column(Price)
    calendar: Mapped[str] = mapped_column(String(24), default="continuous")  # continuous | fx_weekly
    session_tz: Mapped[str] = mapped_column(String(48), default="UTC")
    session_open: Mapped[str] = mapped_column(String(5), default="00:00")  # local daily open HH:MM
    trading_session: Mapped[str | None] = mapped_column(String(200))
    contract_size: Mapped[Decimal] = mapped_column(Price, default=Decimal("1"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict | None] = mapped_column(JSONType)

    provider_links: Mapped[list["ProviderInstrument"]] = relationship(back_populates="instrument")


class DataProvider(Base):
    __tablename__ = "data_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str | None] = mapped_column(String(255))
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict | None] = mapped_column(JSONType)  # limits, licensing, docs links


class ProviderInstrument(Base):
    __tablename__ = "provider_instruments"
    __table_args__ = (UniqueConstraint("provider_id", "instrument_id", name="uq_provider_instrument"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id"))
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    provider_symbol: Mapped[str] = mapped_column(String(48))
    exchange: Mapped[str | None] = mapped_column(String(48))
    market_kind: Mapped[str] = mapped_column(String(24))  # spot | cfd | index | futures
    status: Mapped[str] = mapped_column(String(16))  # active | unverified | unsupported
    notes: Mapped[str | None] = mapped_column(Text)

    provider: Mapped[DataProvider] = relationship()
    instrument: Mapped[Instrument] = relationship(back_populates="provider_links")


class DataCoverage(Base):
    __tablename__ = "data_coverage"
    __table_args__ = (UniqueConstraint("instrument_id", "provider_id", "timeframe", name="uq_coverage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id"))
    timeframe: Mapped[str] = mapped_column(String(4))
    first_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    candle_count: Mapped[int] = mapped_column(Integer, default=0)
    gap_count: Mapped[int] = mapped_column(Integer, default=0)
    gaps: Mapped[list | None] = mapped_column(JSONType)  # [{start, end, missing}]
    last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_sync_status: Mapped[str | None] = mapped_column(String(16))
    last_error: Mapped[str | None] = mapped_column(Text)


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("provider_id", "instrument_id", "timeframe", "ts", name="uq_candle"),
        Index("ix_candle_lookup", "instrument_id", "provider_id", "timeframe", "ts"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id"))
    timeframe: Mapped[str] = mapped_column(String(4))
    ts: Mapped[datetime] = mapped_column(UTCDateTime)  # candle OPEN time, UTC
    open: Mapped[Decimal] = mapped_column(Price)
    high: Mapped[Decimal] = mapped_column(Price)
    low: Mapped[Decimal] = mapped_column(Price)
    close: Mapped[Decimal] = mapped_column(Price)
    volume: Mapped[Decimal | None] = mapped_column(Price)
    volume_type: Mapped[str] = mapped_column(String(8), default="none")  # base | quote | tick | none
    is_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    origin: Mapped[str] = mapped_column(String(12), default="native")  # native | aggregated
    source_meta: Mapped[dict | None] = mapped_column(JSONType)
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
