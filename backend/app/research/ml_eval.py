"""Walk-forward ML evaluation experiments (logistic / LightGBM / XGBoost vs simple baselines)."""
from datetime import datetime, timezone

import numpy as np
from sqlalchemy.orm import Session

from app.feature_engineering.labels import LabelConfig
from app.ml_engine.evaluation import trade_metrics
from app.ml_engine.model_registry import register_model
from app.ml_engine.training import train_and_evaluate
from app.research.strategy_eval import (
    COST_SCENARIOS,
    iso,
    load_series,
    round_trip_cost_frac,
)

ALGOS = ("logistic", "lightgbm", "xgboost")


def run_ml_experiment(session: Session, spec: dict, register: bool = False) -> tuple[dict, dict]:
    """spec: symbol, provider, timeframe, algorithm, label {horizon,tp_atr,sl_atr}, n_splits, threshold,
    cost_scenario, expected_snapshot. Deterministic (fixed seeds)."""
    inst, prov, bars, snap = load_series(session, spec["symbol"], spec.get("provider"), spec["timeframe"],
                                         spec.get("expected_snapshot"))
    lc = spec.get("label", {})
    cfg = LabelConfig(int(lc.get("horizon", 24)), float(lc.get("tp_atr", 2.0)), float(lc.get("sl_atr", 1.0)))
    cost = round_trip_cost_frac(spec.get("cost_scenario", "base"))
    res = train_and_evaluate(bars, spec["algorithm"], cfg, n_splits=int(spec.get("n_splits", 5)), spread=0.0,
                             threshold=float(spec.get("threshold", 0.45)), cost_frac=cost)
    rep = dict(res.report)
    rep["status"] = res.status
    rep["reasons"] = res.reasons
    rep["round_trip_cost_frac"] = cost
    rep["oos_start"] = iso(rep["oos_start_ts"]) if "oos_start_ts" in rep else None
    rep["oos_end"] = iso(rep["oos_end_ts"]) if "oos_end_ts" in rep else None
    for f in rep.get("folds", []):
        f["test_start"], f["test_end"] = iso(f["test_start"]), iso(f["test_end"])
    # keep stored size small: only the long-class reliability curve
    cal = rep.get("calibration", {})
    rep["calibration"] = {"ece": cal.get("ece"), "long": cal.get("long")}
    if register:
        register_model(session, res, inst, prov.id, spec["timeframe"], cfg,
                       datetime.fromtimestamp(int(bars.t[0]), tz=timezone.utc),
                       datetime.fromtimestamp(int(bars.t[-1]), tz=timezone.utc))
    return rep, snap


def rule_engine_in_window(trades_compact: list[dict], oos_start: str | None) -> dict:
    """Rule-engine trades whose entry falls inside the ML out-of-sample window (same period, own stops/targets)."""
    if not oos_start:
        return {"n_trades": 0}
    sel = [t for t in trades_compact if t["entry"] >= oos_start]
    if not sel:
        return {"n_trades": 0}
    return trade_metrics(np.array([t["r"] for t in sel]))


__all__ = ["run_ml_experiment", "rule_engine_in_window", "ALGOS", "COST_SCENARIOS"]
