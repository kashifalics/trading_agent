import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.feature_engineering.labels import LabelConfig
from app.market_data.ingestion.service import resolve_mapping
from app.ml_engine.model_registry import activate_model, register_model
from app.ml_engine.training import ALGORITHMS, train_and_evaluate
from app.services.data_service import ensure_data, load_bars

log = logging.getLogger(__name__)


def train_model(session: Session, params: dict):
    algo = params.get("algorithm", "logistic")
    if algo not in ALGORITHMS:
        raise AppError(f"Unknown algorithm '{algo}'. Choose from {ALGORITHMS}")
    inst, prov, pi = resolve_mapping(session, params["symbol"], params.get("provider"))
    tf = params["timeframe"]
    n = int(params.get("bars", 20000))
    if params.get("auto_sync", True):
        ensure_data(session, inst, prov, pi, tf, n, True)
    bars = load_bars(session, inst, prov, tf, n)
    cfg = LabelConfig(int(params.get("horizon_bars", 24)), float(params.get("tp_atr", 2.0)), float(params.get("sl_atr", 1.0)))
    res = train_and_evaluate(bars, algo, cfg, n_splits=int(params.get("n_splits", 5)),
                             spread=float(params.get("spread", 0.0)), threshold=float(params.get("threshold", 0.45)))
    start = datetime.fromtimestamp(int(bars.t[0]), tz=timezone.utc) if len(bars) else None
    end = datetime.fromtimestamp(int(bars.t[-1]), tz=timezone.utc) if len(bars) else None
    mv = register_model(session, res, inst, prov.id, tf, cfg, start, end)
    if mv.artifact_path:
        activate_model(session, mv)
    return mv


def train_model_job(params: dict) -> None:
    from app.database.session import session_scope

    try:
        with session_scope() as session:
            train_model(session, params)
    except Exception:
        log.exception("model training failed: %s", params)
