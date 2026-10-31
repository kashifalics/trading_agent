"""Chronological, purged walk-forward training with out-of-time probability calibration."""
from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.feature_engineering.labels import LabelConfig
from app.market_data.bars import Bars
from app.ml_engine.calibration import ProbabilityCalibrator
from app.ml_engine.datasets import Dataset, build_dataset
from app.ml_engine.evaluation import (
    calibration_curve,
    log_loss,
    multiclass_brier,
    regime_breakdown,
    simulate_directions,
    simulate_signals,
    trade_metrics,
    validation_status,
)

ALGORITHMS = ("logistic", "lightgbm", "xgboost")


def purged_walk_forward_splits(row_idx: np.ndarray, t1: np.ndarray, n_splits: int = 5,
                               min_train_frac: float = 0.4, embargo: int = 0):
    """Yield (train_pos, test_pos) positions (rows are chronological).
    Train rows are removed when their label window (t1) reaches into the test period (purge) or
    ends within `embargo` bars before it. Train always precedes test: no future data is used."""
    n = len(row_idx)
    start = int(n * min_train_frac)
    edges = np.linspace(start, n, n_splits + 1).astype(int)
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            continue
        test_start_bar = row_idx[a]
        train = np.arange(0, a)
        train = train[t1[train] < test_start_bar - embargo]
        yield train, np.arange(a, b)


class ThreeClassModel:
    """Wraps an sklearn-style classifier; always returns probabilities for all 3 classes."""

    def __init__(self, algorithm: str, seed: int = 0):
        self.algorithm, self.seed = algorithm, seed
        self.est = None
        self.classes_: np.ndarray | None = None

    def _make(self):
        if self.algorithm == "logistic":
            return make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=1000))
        if self.algorithm == "lightgbm":
            from lightgbm import LGBMClassifier
            return LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15, min_child_samples=50,
                                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                                  random_state=self.seed, verbose=-1, n_jobs=2)
        if self.algorithm == "xgboost":
            from xgboost import XGBClassifier
            return XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8,
                                 colsample_bytree=0.8, tree_method="hist", random_state=self.seed, n_jobs=2,
                                 eval_metric="mlogloss", verbosity=0)
        raise ValueError(f"unknown algorithm {self.algorithm}")

    def fit(self, X: np.ndarray, y: np.ndarray) -> "ThreeClassModel":
        self.classes_ = np.unique(y)
        mapping = {c: i for i, c in enumerate(self.classes_)}
        self.est = self._make()
        if len(self.classes_) < 2:
            return self
        self.est.fit(X, np.vectorize(mapping.get)(y))
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        out = np.zeros((len(X), 3))
        if self.est is None or len(self.classes_) < 2:
            out[:, self.classes_[0] if self.classes_ is not None else 1] = 1.0
            return out
        out[:, self.classes_] = self.est.predict_proba(X)
        return out


def _prior_probs(y_train: np.ndarray, n: int) -> np.ndarray:
    p = np.bincount(y_train, minlength=3) / len(y_train)
    return np.tile(p, (n, 1))


def _fit_calibrated(ds_X, ds_y, pos, row_idx, t1, algorithm, cal_frac=0.2):
    """Fit on the first (1-cal_frac) of `pos`, calibrate on the rest (purged between them)."""
    k = int(len(pos) * (1 - cal_frac))
    fit_pos, cal_pos = pos[:k], pos[k:]
    fit_pos = fit_pos[t1[fit_pos] < row_idx[cal_pos[0]]]
    model = ThreeClassModel(algorithm).fit(ds_X[fit_pos], ds_y[fit_pos])
    cal = ProbabilityCalibrator().fit(model.predict_proba(ds_X[cal_pos]), ds_y[cal_pos])
    return model, cal, fit_pos


@dataclass
class TrainResult:
    model: ThreeClassModel
    calibrator: ProbabilityCalibrator
    report: dict
    status: str
    reasons: list[str]
    dataset: Dataset


def train_and_evaluate(bars: Bars, algorithm: str = "logistic", label_cfg: LabelConfig = LabelConfig(),
                       n_splits: int = 5, spread: float = 0.0, threshold: float = 0.45,
                       cost_frac: float = 0.0) -> TrainResult:
    ds = build_dataset(bars, label_cfg)
    n = len(ds.y)
    report: dict = {"algorithm": algorithm, "n_rows": n, "label_config": vars(label_cfg) if hasattr(label_cfg, "__dict__") else {},
                    "class_balance": {c: int((ds.y == i).sum()) for i, c in enumerate(["short", "neither", "long"])}}
    if n < 400:
        report.update(n_oos_rows=0, oos_trades={"n_trades": 0}, error=f"insufficient data: {n} usable rows (< 400)")
        model = ThreeClassModel(algorithm).fit(ds.X, ds.y) if n > 10 else ThreeClassModel(algorithm)
        status, reasons = "research_only", [report["error"]]
        return TrainResult(model, ProbabilityCalibrator(), report, status, reasons, ds)

    P_all, y_all, pos_all, base_all = [], [], [], []
    fold_stats = []
    for train, test in purged_walk_forward_splits(ds.row_idx, ds.t1, n_splits, embargo=label_cfg.horizon // 4):
        if len(train) < 200:
            continue
        model, cal, _ = _fit_calibrated(ds.X, ds.y, train, ds.row_idx, ds.t1, algorithm)
        P = cal.transform(model.predict_proba(ds.X[test]))
        P_all.append(P)
        y_all.append(ds.y[test])
        pos_all.append(test)
        base_all.append(_prior_probs(ds.y[train], len(test)))
        R, _t = simulate_signals(P, ds.row_idx[test], ds.labels, ds.atr[test], spread, threshold,
                                 price=bars.c[ds.row_idx[test]], cost_frac=cost_frac)
        fold_stats.append({"n_train": int(len(train)), "n_test": int(len(test)), **trade_metrics(R),
                           "brier": multiclass_brier(P, ds.y[test]),
                           "test_start": int(bars.t[ds.row_idx[test[0]]]), "test_end": int(bars.t[ds.row_idx[test[-1]]])})
    report["folds"] = fold_stats
    if not P_all:
        report.update(n_oos_rows=0, oos_trades={"n_trades": 0}, error="no walk-forward fold had enough training data")
        return TrainResult(ThreeClassModel(algorithm), ProbabilityCalibrator(), report, "research_only",
                           [report["error"]], ds)

    P, y, pos, base = np.vstack(P_all), np.concatenate(y_all), np.concatenate(pos_all), np.vstack(base_all)
    brier, brier_base = multiclass_brier(P, y), multiclass_brier(base, y)
    R, taken = simulate_signals(P, ds.row_idx[pos], ds.labels, ds.atr[pos], spread, threshold,
                                price=bars.c[ds.row_idx[pos]], cost_frac=cost_frac)
    names = ds.feature_names
    oos_X = ds.X[pos]
    baseline_dirs = {  # simple, parameter-free rules evaluated on EXACTLY the same OOS rows, labels and costs
        "momentum_ret20": np.sign(oos_X[:, names.index("ret_20")]).astype(int),
        "structure_trend": oos_X[:, names.index("structure_trend")].astype(int),
        "always_long": np.ones(len(pos), dtype=int),
    }
    baselines = {}
    for bname, dirs in baseline_dirs.items():
        Rb, _ = simulate_directions(dirs, ds.row_idx[pos], ds.labels, ds.atr[pos], spread, bars.c[ds.row_idx[pos]], cost_frac)
        baselines[bname] = trade_metrics(Rb)
    atr_pct = ds.X[pos, ds.feature_names.index("atr_pct")]
    trend = ds.X[pos, ds.feature_names.index("structure_trend")]
    report.update(
        n_oos_rows=int(len(y)), brier=brier, brier_baseline=brier_base, brier_skill=1 - brier / brier_base,
        log_loss=log_loss(P, y), log_loss_baseline=log_loss(base, y),
        calibration={"long": calibration_curve(P[:, 2], (y == 2).astype(int)),
                     "short": calibration_curve(P[:, 0], (y == 0).astype(int)),
                     "ece": float(np.mean([calibration_curve(P[:, 2], (y == 2).astype(int))["ece"],
                                           calibration_curve(P[:, 0], (y == 0).astype(int))["ece"]]))},
        prediction_coverage=float(len(R) / max(1, len(y))), threshold=threshold, spread=spread,
        oos_trades=trade_metrics(R), baselines=baselines, cost_frac=cost_frac,
        oos_start_ts=int(bars.t[ds.row_idx[pos[0]]]), oos_end_ts=int(bars.t[ds.row_idx[pos[-1]]]),
        by_regime=regime_breakdown(R, taken, atr_pct, trend),
        folds_positive_expectancy=float(np.mean([f.get("expectancy_r", -1) > 0 for f in fold_stats])),
    )
    status, reasons = validation_status(report)
    # Final deployable model: all data, last 20% held for calibration (purged).
    model, cal, _ = _fit_calibrated(ds.X, ds.y, np.arange(n), ds.row_idx, ds.t1, algorithm)
    return TrainResult(model, cal, report, status, reasons, ds)
