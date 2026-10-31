from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.database.models import Instrument, ModelVersion, User
from app.database.session import get_session
from app.jobs.tasks import dispatch
from app.market_data.ingestion.service import resolve_mapping
from app.market_data.timeframes import TIMEFRAMES
from app.ml_engine.model_registry import activate_model
from app.ml_engine.training import ALGORITHMS
from app.schemas.common import Page

router = APIRouter(prefix="/models", tags=["models"])


class TrainRequest(BaseModel):
    symbol: str
    timeframe: str
    algorithm: str = "logistic"
    provider: str | None = None
    bars: int = Field(default=20000, ge=1000, le=100_000)
    horizon_bars: int = Field(default=24, ge=4, le=200)
    tp_atr: float = Field(default=2.0, gt=0.2, le=10)
    sl_atr: float = Field(default=1.0, gt=0.2, le=10)
    spread: float = Field(default=0.0, ge=0)
    n_splits: int = Field(default=5, ge=2, le=10)
    auto_sync: bool = True

    @field_validator("symbol")
    @classmethod
    def _u(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("algorithm")
    @classmethod
    def _a(cls, v: str) -> str:
        if v not in ALGORITHMS:
            raise ValueError(f"algorithm must be one of {ALGORITHMS}")
        return v

    @field_validator("timeframe")
    @classmethod
    def _t(cls, v: str) -> str:
        if v not in TIMEFRAMES:
            raise ValueError("unsupported timeframe")
        return v


def _row(session: Session, m: ModelVersion, full: bool = False) -> dict:
    inst = session.get(Instrument, m.instrument_id) if m.instrument_id else None
    metrics = m.metrics or {}
    d = {"id": m.id, "name": m.name, "algorithm": m.algorithm, "symbol": inst.canonical_symbol if inst else None,
         "timeframe": m.timeframe, "version": m.version, "trained_at": m.trained_at, "n_samples": m.n_samples,
         "data_start": m.data_start, "data_end": m.data_end, "validation_status": m.validation_status,
         "validation_reasons": m.validation_reasons, "is_calibrated": m.is_calibrated, "is_active": m.is_active,
         "summary": {k: metrics.get(k) for k in ("n_oos_rows", "brier", "brier_baseline", "brier_skill",
                                                 "prediction_coverage", "error")},
         "oos_trades": metrics.get("oos_trades")}
    if full:
        d["metrics"] = metrics
        d["feature_names"] = m.feature_names
        d["label_config"] = m.label_config
    return d


@router.get("", response_model=Page[dict])
def list_models(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), session: Session = Depends(get_session)):
    total = session.scalar(select(func.count()).select_from(ModelVersion))
    rows = session.scalars(select(ModelVersion).order_by(ModelVersion.id.desc()).limit(limit).offset(offset)).all()
    return Page(items=[_row(session, m) for m in rows], total=total, limit=limit, offset=offset)


@router.get("/{model_id}")
def get_model(model_id: int, session: Session = Depends(get_session)) -> dict:
    m = session.get(ModelVersion, model_id)
    if not m:
        raise NotFoundError("Model not found")
    return _row(session, m, full=True)


@router.post("/train", status_code=202)
def train(req: TrainRequest, background: BackgroundTasks, session: Session = Depends(get_session),
          user: User = Depends(get_current_user)) -> dict:
    resolve_mapping(session, req.symbol, req.provider)  # fail fast on unsupported instruments
    dispatch("train_model", background, req.model_dump())
    return {"status": "queued", "note": "Training runs in the background; the model appears in GET /models when done. "
                                         "Research-only unless it passes minimum out-of-sample checks."}


@router.post("/{model_id}/activate")
def activate(model_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    m = session.get(ModelVersion, model_id)
    if not m or not m.artifact_path:
        raise NotFoundError("Model not found or has no artifact")
    activate_model(session, m)
    return _row(session, m)
