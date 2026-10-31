from datetime import datetime, timezone
from pathlib import Path

import joblib
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import Instrument, ModelVersion
from app.feature_engineering.labels import LabelConfig
from app.ml_engine.training import TrainResult


def register_model(session: Session, res: TrainResult, inst: Instrument, provider_id: int, timeframe: str,
                   label_cfg: LabelConfig, data_start: datetime | None, data_end: datetime | None) -> ModelVersion:
    algo = res.report["algorithm"]
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    path = None
    if res.report.get("n_oos_rows", 0) > 0:
        d = Path(get_settings().model_dir)
        d.mkdir(parents=True, exist_ok=True)
        path = str(d / f"{inst.canonical_symbol}_{timeframe}_{algo}_{version}.joblib")
        joblib.dump({"model": res.model, "calibrator": res.calibrator, "feature_names": res.dataset.feature_names,
                     "label_cfg": vars(label_cfg)}, path)
    mv = ModelVersion(
        name=f"{inst.canonical_symbol}-{timeframe}-{algo}", algorithm=algo, instrument_id=inst.id,
        provider_id=provider_id, timeframe=timeframe, version=version, n_samples=res.report["n_rows"],
        data_start=data_start, data_end=data_end, feature_names=res.dataset.feature_names,
        label_config=vars(label_cfg), metrics=res.report, validation_status=res.status,
        validation_reasons=res.reasons, is_calibrated=path is not None and res.calibrator.method != "identity",
        artifact_path=path,
    )
    session.add(mv)
    session.commit()
    return mv


def activate_model(session: Session, mv: ModelVersion) -> None:
    session.execute(update(ModelVersion).where(
        ModelVersion.instrument_id == mv.instrument_id, ModelVersion.provider_id == mv.provider_id,
        ModelVersion.timeframe == mv.timeframe).values(is_active=False))
    mv.is_active = True
    session.commit()


def get_active_model(session: Session, instrument_id: int, provider_id: int, timeframe: str) -> ModelVersion | None:
    return session.scalar(select(ModelVersion).where(
        ModelVersion.instrument_id == instrument_id, ModelVersion.provider_id == provider_id,
        ModelVersion.timeframe == timeframe, ModelVersion.is_active.is_(True)))
