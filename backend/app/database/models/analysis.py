from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, utcnow
from app.database.types import BigIntPK, JSONType, Price, UTCDateTime


class Screenshot(Base):
    __tablename__ = "screenshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(32))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ChartExtraction(Base):
    __tablename__ = "chart_extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screenshot_id: Mapped[int] = mapped_column(ForeignKey("screenshots.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id"))
    status: Mapped[str] = mapped_column(String(16))
    ocr_available: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_symbol: Mapped[str | None] = mapped_column(String(32))
    detected_timeframe: Mapped[str | None] = mapped_column(String(4))
    price_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    calibration: Mapped[dict | None] = mapped_column(JSONType)
    candles: Mapped[list | None] = mapped_column(JSONType)
    quality_score: Mapped[float | None] = mapped_column(Float)
    quality_breakdown: Mapped[dict | None] = mapped_column(JSONType)
    market_match: Mapped[dict | None] = mapped_column(JSONType)
    warnings: Mapped[list | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id"))
    timeframe: Mapped[str] = mapped_column(String(4))
    source: Mapped[str] = mapped_column(String(16), default="market_data")  # market_data | screenshot
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)
    params: Mapped[dict | None] = mapped_column(JSONType)
    result: Mapped[dict | None] = mapped_column(JSONType)
    error: Mapped[str | None] = mapped_column(Text)
    as_of_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PriceActionEvent(Base):
    __tablename__ = "price_action_events"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    timeframe: Mapped[str] = mapped_column(String(4))
    kind: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    level_low: Mapped[Decimal | None] = mapped_column(Price)
    level_high: Mapped[Decimal | None] = mapped_column(Price)
    status: Mapped[str | None] = mapped_column(String(16))
    evidence: Mapped[dict | None] = mapped_column(JSONType)


class HistoricalAnalogue(Base):
    __tablename__ = "historical_analogues"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    matched_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    similarity: Mapped[float] = mapped_column(Float)  # NOT a probability
    horizon_bars: Mapped[int] = mapped_column(Integer)
    forward_return: Mapped[float | None] = mapped_column(Float)
    mfe_atr: Mapped[float | None] = mapped_column(Float)
    mae_atr: Mapped[float | None] = mapped_column(Float)
    long_tp_before_sl: Mapped[bool | None] = mapped_column(Boolean)
    short_tp_before_sl: Mapped[bool | None] = mapped_column(Boolean)
    meta: Mapped[dict | None] = mapped_column(JSONType)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    algorithm: Mapped[str] = mapped_column(String(24))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id"))
    timeframe: Mapped[str] = mapped_column(String(4))
    version: Mapped[str] = mapped_column(String(32))
    trained_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    n_samples: Mapped[int] = mapped_column(Integer)
    data_start: Mapped[datetime | None] = mapped_column(UTCDateTime)
    data_end: Mapped[datetime | None] = mapped_column(UTCDateTime)
    feature_names: Mapped[list | None] = mapped_column(JSONType)
    label_config: Mapped[dict | None] = mapped_column(JSONType)
    metrics: Mapped[dict | None] = mapped_column(JSONType)
    validation_status: Mapped[str] = mapped_column(String(24), default="research_only")
    validation_reasons: Mapped[list | None] = mapped_column(JSONType)
    is_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    artifact_path: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    provider_code: Mapped[str | None] = mapped_column(String(32))
    timeframe: Mapped[str] = mapped_column(String(4))
    decision: Mapped[str] = mapped_column(String(4), index=True)  # BUY | SELL | WAIT
    entry_low: Mapped[Decimal | None] = mapped_column(Price)
    entry_high: Mapped[Decimal | None] = mapped_column(Price)
    stop_loss: Mapped[Decimal | None] = mapped_column(Price)
    take_profit: Mapped[list | None] = mapped_column(JSONType)
    risk_reward: Mapped[float | None] = mapped_column(Float)
    invalidation_level: Mapped[Decimal | None] = mapped_column(Price)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    probabilities: Mapped[dict | None] = mapped_column(JSONType)  # only when genuinely calibrated
    historical_frequency: Mapped[dict | None] = mapped_column(JSONType)
    confluence_score: Mapped[float | None] = mapped_column(Float)
    data_quality_score: Mapped[float | None] = mapped_column(Float)
    warnings: Mapped[list | None] = mapped_column(JSONType)
    explanation: Mapped[str | None] = mapped_column(Text)
    as_of_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    outcome: Mapped[str] = mapped_column(String(16), default="open")  # open|tp_hit|sl_hit|expired|not_applicable
    outcome_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    outcome_meta: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class PredictionEvidence(Base):
    __tablename__ = "prediction_evidence"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(8))
    weight: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)  # signed contribution in [-1, 1] x weight
    detail: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    price: Mapped[Decimal | None] = mapped_column(Price)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id"))
    timeframe: Mapped[str] = mapped_column(String(4))
    strategy: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(12), default="queued")
    config: Mapped[dict | None] = mapped_column(JSONType)
    metrics: Mapped[dict | None] = mapped_column(JSONType)
    equity_curve: Mapped[list | None] = mapped_column(JSONType)
    start_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    end_ts: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(5))
    signal_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    entry_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    entry_price: Mapped[Decimal] = mapped_column(Price)
    exit_ts: Mapped[datetime] = mapped_column(UTCDateTime)
    exit_price: Mapped[Decimal] = mapped_column(Price)
    exit_reason: Mapped[str] = mapped_column(String(16))
    stop_loss: Mapped[Decimal] = mapped_column(Price)
    take_profit: Mapped[Decimal | None] = mapped_column(Price)
    units: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float)
    r_multiple: Mapped[float] = mapped_column(Float)
    costs: Mapped[float] = mapped_column(Float)


class IngestionRun(Base):
    """One historical backfill / sync execution: what was asked, what the provider actually returned."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), index=True)
    timeframe: Mapped[str] = mapped_column(String(4))
    kind: Mapped[str] = mapped_column(String(12))  # backfill | sync
    status: Mapped[str] = mapped_column(String(12), default="running")  # running | completed | partial | failed
    range_start: Mapped[datetime | None] = mapped_column(UTCDateTime)
    range_end: Mapped[datetime | None] = mapped_column(UTCDateTime)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    stored: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    misaligned: Mapped[int] = mapped_column(Integer, default=0)
    missing_before: Mapped[int] = mapped_column(Integer, default=0)
    missing_after: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSONType)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Experiment(Base):
    """A reproducible research run: dataset snapshot + full configuration + code/library versions + results."""

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # backtest | baseline | ml
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(12), default="completed")
    dataset: Mapped[dict | None] = mapped_column(JSONType)
    config: Mapped[dict | None] = mapped_column(JSONType)
    code_version: Mapped[dict | None] = mapped_column(JSONType)
    results: Mapped[dict | None] = mapped_column(JSONType)
    duration_s: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
