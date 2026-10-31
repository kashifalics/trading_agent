from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.market_data.timeframes import TIMEFRAMES
from app.schemas.common import ORM, MTFConfigIn


class AnalysisRunRequest(BaseModel):
    symbol: str = Field(min_length=3, max_length=32)
    timeframe: str
    provider: str | None = None
    mtf: MTFConfigIn = Field(default_factory=MTFConfigIn)
    lookback_bars: int = Field(default=1500, ge=200, le=20_000)
    auto_sync: bool = True
    horizon_bars: int = Field(default=24, ge=4, le=200)
    tp_atr: float = Field(default=2.0, gt=0.2, le=10)
    sl_atr: float = Field(default=1.0, gt=0.2, le=10)
    min_rr: float = Field(default=1.5, ge=1.0, le=10)
    use_ml: bool = True

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("timeframe")
    @classmethod
    def _tf(cls, v: str) -> str:
        if v not in TIMEFRAMES:
            raise ValueError(f"unsupported timeframe; use one of {list(TIMEFRAMES)}")
        return v


class AnalysisOut(ORM):
    id: int
    instrument_id: int
    timeframe: str
    source: str
    status: str
    params: dict | None
    result: dict | None
    error: str | None
    as_of_ts: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    prediction_id: int | None = None
    symbol: str | None = None


class EvidenceOut(ORM):
    category: str
    name: str
    direction: str
    weight: float
    score: float
    detail: str | None
    ts: datetime | None
    price: float | None


class PredictionOut(ORM):
    id: int
    analysis_id: int
    symbol: str | None = None
    instrument_id: int
    provider_code: str | None
    timeframe: str
    decision: str
    entry_low: float | None
    entry_high: float | None
    stop_loss: float | None
    take_profit: list | None
    risk_reward: float | None
    invalidation_level: float | None
    model_version_id: int | None
    probabilities: dict | None
    historical_frequency: dict | None
    confluence_score: float | None
    data_quality_score: float | None
    warnings: list | None
    explanation: str | None
    as_of_ts: datetime
    outcome: str
    outcome_ts: datetime | None
    outcome_meta: dict | None
    created_at: datetime


class PredictionDetail(PredictionOut):
    evidence: list[EvidenceOut] = []
    confidence: dict | None = None
    wait_reasons: list[str] = []
