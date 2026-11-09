"""Phase 5: supervised models on the event-level trade dataset (brief Parts 9-12). Research only: nothing here trades.

Rows: training-segment trades of a setup timeframe (identical orders on the same candle collapsed to one row). Every feature is
taken at the signal candle's close from point-in-time arrays (causal; tested by truncation). Labels: the pre-defined trade plan
(entry, structural stop) reaches kR before the stop within 48 candles, for k = 1, 1.5, 2 (primary), 3; and the R of the 2R plan.

Validation inside the training segment only:
  * purged walk-forward on time (5 expanding folds; a rolling-window variant is reported too): training rows whose outcome
    window (48 candles) reaches the test block are dropped, plus an embargo of the same length after it;
  * nested model selection: hyperparameters are chosen on the last 20% (purged) of each outer training block, never on the
    test block;
  * calibration: isotonic, fitted for each fold only on out-of-fold predictions of EARLIER folds (cross-fitted), so the
    calibrated metrics are honest; the final calibrator uses all out-of-fold predictions.
The validation segment is used once, on the frozen model (ml-validate). Models are registered as challengers in
data/historical/research/{SYMBOL}/models/; the champion pointer changes only through `promote --approve` (never automatically).
"""
import hashlib
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import polars as pl
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from app.feature_engineering.indicators import atr as atr_fn
from app.feature_engineering.indicators import ema
from app.gold_research import combos, regimes, sim
from app.gold_research.events import bars_from_frame
from app.historical.config import TF_SECONDS
from app.historical.split import load_split
from app.historical.store import load_tf
from app.historical.sync import bar_close
from app.market_structure.swings import find_swings
from app.ml_engine.evaluation import calibration_curve, trade_metrics
from app.patterns.candles import _roll_max, _roll_min, _sh
from app.patterns.context import compute_levels
from app.patterns.registry import FAMILIES, REGISTRY

ML_TFS = ("M15", "H1", "H4")
HOLD = 48
LABEL_TARGETS = (1.0, 1.5, 2.0, 3.0)
PRIMARY_K = 2.0
N_FOLDS = 5
SEED = 7
LGBM_GRID = [
    {"num_leaves": 15, "min_child_samples": 200, "learning_rate": 0.05, "colsample_bytree": 0.8},
    {"num_leaves": 31, "min_child_samples": 200, "learning_rate": 0.05, "colsample_bytree": 0.8},
    {"num_leaves": 63, "min_child_samples": 500, "learning_rate": 0.05, "colsample_bytree": 0.6},
    {"num_leaves": 15, "min_child_samples": 1000, "learning_rate": 0.03, "colsample_bytree": 0.6},
]
CATEGORICAL = ["pattern_code", "family_code", "trend_regime", "range_regime", "vol_level", "structural_regime", "session", "near_level"]
PATTERN_CODE = {k: i for i, k in enumerate(sorted(REGISTRY))}
FAMILY_CODE = {k: i for i, k in enumerate(FAMILIES)}


# ------------------------------------------------------------------ features
def _codes(x: np.ndarray) -> np.ndarray:
    cats = {v: i for i, v in enumerate(sorted({str(v) for v in x}))}
    return np.array([cats[str(v)] for v in x], dtype=np.int32)


def build_features(symbol: str, tf: str, segment: str, trades: pl.DataFrame, events: pl.DataFrame | None = None,
                   prior_trades: pl.DataFrame | None = None) -> pl.DataFrame:
    """Feature matrix (one row per trade, same order). Uses candles of `segment` only (sealed loader)."""
    df = load_tf(symbol, tf, upto=segment)
    b = bars_from_frame(df, TF_SECONDS[tf])
    o, h, lo, c = b.o, b.h, b.l, b.c
    n = len(c)
    a = atr_fn(h, lo, c, 14)
    idx = trades["idx"].to_numpy()
    d = trades["direction"].to_numpy().astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        rng = np.where(h - lo > 0, h - lo, np.nan)
        e50 = ema(c, 50)
        up = c > o
        run = np.zeros(n)
        for i in range(1, n):
            run[i] = run[i - 1] + 1 if up[i] == up[i - 1] else 1
        run_signed = np.where(up, run, -run)
        per_bar = {
            "body_pct": np.abs(c - o) / rng, "upper_wick": (h - np.maximum(o, c)) / rng, "lower_wick": (np.minimum(o, c) - lo) / rng,
            "range_atr": rng / a, "ret_1": (c - _sh(c, 1)) / a, "ret_5": (c - _sh(c, 5)) / a, "ret_20": (c - _sh(c, 20)) / a,
            "run": run_signed, "compression5": (_roll_max(h, 5) - _roll_min(lo, 5)) / a,
            "disp3": _roll_max(np.abs(c - o), 3) / a, "slope50": (e50 - _sh(e50, 20)) / a, "dist_ema50": (c - e50) / a,
            "atr_bps": a / c * 1e4, "atr_ratio": a / atr_fn(h, lo, c, 100),
        }
        path = np.convolve(np.abs(np.r_[0.0, np.diff(c)]), np.ones(20), "full")[:n]
        per_bar["er20"] = np.abs(c - _sh(c, 20)) / path
        sw = find_swings(b)
        last_hi, last_lo = np.full(n, np.nan), np.full(n, np.nan)
        for s in sorted(sw, key=lambda s: s.confirm_idx):
            if s.confirm_idx < n:
                (last_hi if s.kind == "high" else last_lo)[s.confirm_idx] = s.price
        last_hi = pl.Series(last_hi).fill_null(strategy="forward").fill_nan(None).fill_null(strategy="forward").to_numpy()
        last_lo = pl.Series(last_lo).fill_null(strategy="forward").fill_nan(None).fill_null(strategy="forward").to_numpy()
        per_bar["swing_hi_dist"] = (last_hi - c) / a
        per_bar["swing_lo_dist"] = (c - last_lo) / a
        lv = compute_levels(df["ts"], bar_close(tf, b.t), h, lo)
        for k in ("pdh", "pdl", "pwh", "pwl"):
            per_bar[f"dist_{k}"] = (getattr(lv, k) - c) / a
        from app.patterns.ctx import (
            ChunkCtx,  # noqa: F401  (documentation: same arrays the detectors see)
        )
        trend_struct = np.zeros(n, dtype=np.int8)
        reg = regimes.compute(b.t, o, h, lo, c, a, trend_struct, lv, None)
    X = {}
    signed = {"ret_1", "ret_5", "ret_20", "run", "slope50", "dist_ema50"}
    for k, v in per_bar.items():
        x = v[idx]
        X[k] = x * d if k in signed else x
    X["fav_wick"] = np.where(d > 0, X["lower_wick"], X["upper_wick"])  # wick on the side the trade is protected by
    X["adv_wick"] = np.where(d > 0, X["upper_wick"], X["lower_wick"])
    X["room_to_opposing_swing"] = np.where(d > 0, X["swing_hi_dist"], X["swing_lo_dist"])
    X["room_to_opposing_pd"] = np.where(d > 0, X["dist_pdh"], -X["dist_pdl"])
    for k in ("trend_regime", "range_regime", "vol_level", "structural_regime", "session", "near_level"):
        X[k] = _codes(np.asarray(reg[k])[idx])
    tr = trades
    X["pattern_code"] = np.array([PATTERN_CODE.get(p, -1) for p in tr["pattern"].to_list()], dtype=np.int32)
    X["family_code"] = np.array([FAMILY_CODE.get(REGISTRY[p].family, -1) if p in REGISTRY else -1 for p in tr["pattern"].to_list()],
                                dtype=np.int32)
    X["limit_entry"] = (tr["entry"] == "limit").to_numpy().astype(float)
    X["risk_atr"] = tr["risk_atr"].to_numpy()
    nyh = pl.Series((tr["signal_ts"].to_numpy() * 1_000_000).astype("datetime64[us]")).dt.replace_time_zone("UTC").dt.convert_time_zone(
        "America/New_York")
    X["hour_ny"] = nyh.dt.hour().to_numpy().astype(float)
    X["weekday"] = nyh.dt.weekday().to_numpy().astype(float)
    if events is not None:  # recent pattern activity by family, aligned with / against the trade (last 10 candles)
        fam_of = {k: s.family for k, s in REGISTRY.items()}
        ev = events.with_columns(fam=pl.col("pattern").replace_strict(fam_of, default="?"))
        for fam in FAMILIES:
            for side, sgn in (("with", 1), ("against", -1)):
                cnt = np.zeros(n + 1)
                for dd in (1, -1):
                    e = ev.filter((pl.col("fam") == fam) & (pl.col("direction") == dd))["idx"].to_numpy()
                    cum = np.zeros(n + 1)
                    np.add.at(cum, np.clip(e, 0, n - 1) + 1, 1)
                    cum = np.cumsum(cum)
                    cnt_dd = cum[np.minimum(idx + 1, n)] - cum[np.maximum(idx - 9, 0)]
                    X.setdefault(f"recent_{fam}_{side}", np.zeros(len(idx)))
                    X[f"recent_{fam}_{side}"] = X[f"recent_{fam}_{side}"] + np.where(d * dd * sgn > 0, cnt_dd, 0)
                del cnt
    p = next((p for p in combos.PROFILES.values() if p["setup"] == tf), None)
    if p is not None:  # higher-timeframe state at the signal close
        sig_close = tr["signal_ts"].to_numpy() + TF_SECONDS[tf]
        for role in ("bias", "context", "confirm"):
            try:
                st = combos.tf_state(symbol, p[role], segment)
            except FileNotFoundError:
                continue
            j = np.searchsorted(st["close"], sig_close, side="right") - 1
            ok = j >= 0
            jj = np.maximum(j, 0)
            X[f"htf_{role}_trend"] = np.where(ok, st["trend"][jj], 0) * d
            X[f"htf_{role}_regime"] = np.where(ok, st["regime"][jj], 0) * d
            if role == "confirm":
                X["htf_confirm_break"] = np.where(ok, st["break_dir"][jj], 0) * d
    X["pattern_prior_r"] = pattern_prior(tr, prior_trades, tf)
    return pl.DataFrame({k: np.asarray(v, dtype=np.float64 if k not in CATEGORICAL else np.int32) for k, v in X.items()})


def pattern_prior(trades: pl.DataFrame, earlier: pl.DataFrame | None, tf: str) -> np.ndarray:
    """Mean R (2R plan) of the same pattern and direction over trades whose outcome window had ENDED before this trade's entry
    (expanding, causal). `earlier` adds trades from previous segments (e.g. training rows when building validation features)."""
    hold_s = HOLD * TF_SECONDS[tf]
    pool = trades if earlier is None else pl.concat([earlier.select(trades.columns), trades], how="vertical_relaxed")
    r = _r2(pool)
    key = (pool["pattern"] + ":" + pool["direction"].cast(pl.Utf8)).to_numpy()
    done = pool["entry_ts"].to_numpy() + hold_s
    out = np.full(trades.height, np.nan)
    tkey = (trades["pattern"] + ":" + trades["direction"].cast(pl.Utf8)).to_numpy()
    tent = trades["entry_ts"].to_numpy()
    for k in np.unique(tkey):
        m = key == k
        order = np.argsort(done[m])
        dsort, rsort = done[m][order], np.nan_to_num(r[m][order])
        cum = np.r_[0.0, np.cumsum(rsort)]
        sel = np.flatnonzero(tkey == k)
        cnt = np.searchsorted(dsort, tent[sel], side="right")
        out[sel] = np.where(cnt >= 30, cum[cnt] / np.maximum(cnt, 1), np.nan)
    return out


def _r2(t: pl.DataFrame, k: float = PRIMARY_K) -> np.ndarray:
    o = {"simulated": np.ones(t.height, bool), "stop_r": t["stop_r"].to_numpy(), f"mfe_{HOLD}": t[f"mfe_{HOLD}"].to_numpy(),
         f"mfe_opt_{HOLD}": t[f"mfe_opt_{HOLD}"].to_numpy(), f"stopped_{HOLD}": t[f"stopped_{HOLD}"].to_numpy(),
         f"end_r_{HOLD}": t[f"end_r_{HOLD}"].to_numpy()}
    return sim.r_multiple(o, k, HOLD)


def dataset(trades: pl.DataFrame) -> pl.DataFrame:
    """One row per distinct order: identical (direction, entry candle, stop) from different patterns collapse to the first."""
    t = trades.with_columns(pl.col("risk_px").round(6).alias("_rk"))
    return t.unique(subset=["direction", "fill_bar", "_rk"], keep="first", maintain_order=True).drop("_rk") if "fill_bar" in t.columns \
        else t.unique(subset=["direction", "entry_ts", "_rk"], keep="first", maintain_order=True).drop("_rk")


def labels(t: pl.DataFrame) -> dict[str, np.ndarray]:
    out = {f"y_{k:g}R": (t[f"mfe_{HOLD}"].to_numpy() >= k).astype(int) for k in LABEL_TARGETS}
    out["r2"] = _r2(t)
    out["mfe"] = t[f"mfe_{HOLD}"].to_numpy()
    return out


# ------------------------------------------------------------------ validation
def purged_folds(entry_ts: np.ndarray, hold_s: int, n_folds: int = N_FOLDS, rolling: bool = False, min_train_frac: float = 0.3):
    """Chronological folds: (train_idx, test_idx). Train rows end their outcome window before the test block starts; rows inside an
    embargo of one holding period after the test block are excluded from later training blocks."""
    order = np.argsort(entry_ts, kind="stable")
    ts = entry_ts[order]
    n = len(ts)
    start = int(n * min_train_frac)
    bounds = np.linspace(start, n, n_folds + 1).astype(int)
    first_len = None
    for f in range(n_folds):
        a, z = bounds[f], bounds[f + 1]
        if z <= a:
            continue
        t0, t1 = ts[a], ts[z - 1]
        train = order[(ts + hold_s < t0)]
        if rolling:
            first_len = first_len or len(train)
            train = train[-first_len:]
        test = order[a:z]
        yield train, test, (int(t0), int(t1))


def _model(kind: str, params: dict | None = None):
    if kind == "logistic":
        return LogisticRegression(C=0.1, max_iter=500)
    if kind in ("lgbm", "lgbm_rf"):
        import lightgbm as lgb
        p = {"n_estimators": 400, "subsample": 0.8, "subsample_freq": 1, "random_state": SEED, "n_jobs": 1, "verbose": -1,
             **(params or LGBM_GRID[0])}
        if kind == "lgbm_rf":
            p.update(boosting_type="rf", n_estimators=300, learning_rate=1.0, subsample=0.632, colsample_bytree=0.6)
        return lgb.LGBMClassifier(**p)
    if kind == "xgb":
        import xgboost as xgb
        return xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                                 min_child_weight=50, random_state=SEED, n_jobs=1, eval_metric="logloss", tree_method="hist")
    raise ValueError(kind)


def _prep(X: pl.DataFrame, kind: str, scaler=None):
    A = X.to_numpy().astype(float)
    if kind == "logistic":
        A = np.nan_to_num(A, nan=0.0)
        cats = [X.columns.index(c) for c in CATEGORICAL if c in X.columns]
        num = [i for i in range(A.shape[1]) if i not in cats]
        if scaler is None:
            scaler = StandardScaler().fit(A[:, num])
        A = np.c_[scaler.transform(A[:, num]), _onehot(A[:, cats])]
        return A, scaler
    return A, None


def _onehot(C: np.ndarray, max_levels: int = 40) -> np.ndarray:
    cols = []
    for j in range(C.shape[1]):
        for v in range(max_levels):
            cols.append((C[:, j] == v).astype(float))
    return np.stack(cols, 1) if cols else np.zeros((len(C), 0))


def _fit_predict(kind: str, Xtr, ytr, Xte, params=None):
    A, sc = _prep(Xtr, kind)
    B, _ = _prep(Xte, kind, sc)
    m = _model(kind, params)
    if len(np.unique(ytr)) < 2:
        return np.full(len(B), float(ytr.mean())), m
    m.fit(A, ytr)
    return m.predict_proba(B)[:, 1], (m, sc)


def _select_params(Xtr: pl.DataFrame, ytr: np.ndarray, ts_tr: np.ndarray, hold_s: int) -> dict:
    """Nested: choose LightGBM parameters on the last 20% of the outer training block (purged), by log loss."""
    order = np.argsort(ts_tr)
    cut = order[int(len(order) * 0.8)]
    t0 = ts_tr[cut]
    inner_tr = np.flatnonzero(ts_tr + hold_s < t0)
    inner_va = np.flatnonzero(ts_tr >= t0)
    if len(inner_tr) < 500 or len(inner_va) < 200 or len(np.unique(ytr[inner_va])) < 2:
        return LGBM_GRID[0]
    best, best_ll = LGBM_GRID[0], np.inf
    for p in LGBM_GRID:
        pr, _ = _fit_predict("lgbm", Xtr[inner_tr], ytr[inner_tr], Xtr[inner_va], p)
        ll = log_loss(ytr[inner_va], np.clip(pr, 1e-6, 1 - 1e-6))
        if ll < best_ll:
            best, best_ll = p, ll
    return best


def metrics(y: np.ndarray, p: np.ndarray, r: np.ndarray) -> dict:
    ok = np.isfinite(p)
    y, p, r = y[ok], p[ok], r[ok]
    out = {"n": int(len(y)), "base_rate": float(y.mean()) if len(y) else None}
    if len(np.unique(y)) == 2:
        out.update(roc_auc=float(roc_auc_score(y, p)), pr_auc=float(average_precision_score(y, p)),
                   brier=float(brier_score_loss(y, p)), log_loss=float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))),
                   brier_skill=float(1 - brier_score_loss(y, p) / max(brier_score_loss(y, np.full(len(y), y.mean())), 1e-12)),
                   ece=calibration_curve(p, y)["ece"])
    sel = {}
    for name, m in (("all", np.ones(len(p), bool)), ("p>=0.4", p >= 0.4), ("p>=0.5", p >= 0.5), ("top_decile", p >= np.quantile(p, 0.9) if len(p) else p)):
        if m.sum() >= 30:
            tp = (y[m] == 1).sum()
            sel[name] = {**trade_metrics(r[m][np.isfinite(r[m])]), "precision": float(tp / m.sum()),
                         "recall": float(tp / max(y.sum(), 1)), "f1": float(2 * tp / max(m.sum() + y.sum(), 1))}
    out["selection"] = sel
    return out


def walk_forward(X: pl.DataFrame, y: np.ndarray, r: np.ndarray, ts: np.ndarray, hold_s: int, kind: str, nested: bool = True,
                 rolling: bool = False) -> dict:
    oof = np.full(len(y), np.nan)
    cal = np.full(len(y), np.nan)
    folds = []
    params_used = []
    for train, test, span in purged_folds(ts, hold_s, rolling=rolling):
        params = _select_params(X[train], y[train], ts[train], hold_s) if (kind == "lgbm" and nested) else None
        params_used.append(params)
        pr, _ = _fit_predict(kind, X[train], y[train], X[test], params)
        oof[test] = pr
        earlier = np.flatnonzero(np.isfinite(oof) & (ts < span[0]))  # cross-fitted calibration on earlier folds only
        if len(earlier) >= 1000 and len(np.unique(y[earlier])) == 2:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(oof[earlier], y[earlier])
            cal[test] = iso.predict(pr)
        folds.append({"span": [datetime.fromtimestamp(span[0], timezone.utc).date().isoformat(),
                               datetime.fromtimestamp(span[1], timezone.utc).date().isoformat()], "n_train": int(len(train)),
                      "n_test": int(len(test)), **{k: v for k, v in metrics(y[test], pr, r[test]).items() if k != "selection"}})
    return {"kind": kind, "rolling": rolling, "folds": folds, "oof": metrics(y, oof, r), "oof_calibrated": metrics(y, cal, r),
            "params": params_used, "_oof": oof}


# ------------------------------------------------------------------ orchestration
def models_dir(symbol: str):
    from app.gold_research.study import out_dir
    return out_dir(symbol) / "models"


def train(symbol: str, tfs=ML_TFS, kinds=("logistic", "lgbm", "lgbm_rf", "xgb"), log=print) -> dict:
    from app.gold_research.study import out_dir
    summary = {"symbol": symbol, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "split_sha256": load_split(symbol)["sha256"],
               "label_primary": f"{PRIMARY_K:g}R before stop within {HOLD} candles", "tfs": {}}
    for tf in tfs:
        p = out_dir(symbol) / f"trades_{tf}_train.parquet"
        if not p.exists():
            log(f"{tf}: no training trades, skipped")
            continue
        tr = dataset(pl.read_parquet(p)).sort("entry_ts")
        evp = out_dir(symbol) / f"events_{tf}_train.parquet"
        X = build_features(symbol, tf, "train", tr, pl.read_parquet(evp) if evp.exists() else None)
        lab = labels(tr)
        ts = tr["entry_ts"].to_numpy()
        hold_s = HOLD * TF_SECONDS[tf]
        res = {"rows": tr.height, "features": X.columns, "models": {}}
        y = lab[f"y_{PRIMARY_K:g}R"]
        for kind in kinds:
            log(f"{tf}: walk-forward {kind} ({tr.height:,} rows, {X.width} features)")
            res["models"][kind] = walk_forward(X, y, lab["r2"], ts, hold_s, kind)
        res["models"]["lgbm_rolling"] = walk_forward(X, y, lab["r2"], ts, hold_s, "lgbm", rolling=True)
        for k in LABEL_TARGETS:
            if k != PRIMARY_K:
                log(f"{tf}: walk-forward lgbm for {k:g}R")
                res["models"][f"lgbm_{k:g}R"] = walk_forward(X, lab[f"y_{k:g}R"], _r2(tr, k), ts, hold_s, "lgbm", nested=False)
        shuffled = np.random.default_rng(SEED).permutation(y)  # leakage check: labels shuffled -> no skill expected
        res["shuffled_label_check"] = walk_forward(X, shuffled, lab["r2"], ts, hold_s, "lgbm", nested=False)["oof"]
        best = min((k for k in kinds), key=lambda k: res["models"][k]["oof"].get("log_loss", np.inf))
        res["best_kind"] = best
        res["challenger"] = register(symbol, tf, X, y, lab["r2"], ts, hold_s, best, res["models"][best], log)
        for m in res["models"].values():
            m.pop("_oof", None)
        summary["tfs"][tf] = res
    out = out_dir(symbol) / "ml_training.json"
    out.write_text(json.dumps(summary, indent=1, default=float), encoding="utf8")
    return summary


def register(symbol, tf, X, y, r, ts, hold_s, kind, wf, log) -> str:
    """Fit the chosen model on all training rows and save it with its calibrator as a challenger (never the champion)."""
    params = None
    if kind == "lgbm":
        params = _select_params(X, y, ts, hold_s)
    A, sc = _prep(X, kind)
    m = _model(kind, params)
    m.fit(A, y)
    oof = wf["_oof"]
    ok = np.isfinite(oof)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(oof[ok], y[ok])
    version = f"{tf}-{kind}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
    d = models_dir(symbol) / version
    d.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": m, "scaler": sc, "calibrator": iso, "features": X.columns, "kind": kind, "params": params, "tf": tf,
                 "label": f"{PRIMARY_K:g}R before stop within {HOLD} candles"}, d / "model.joblib")
    meta = {"version": version, "tf": tf, "kind": kind, "status": "challenger", "params": params,
            "walk_forward_oof": wf["oof"], "walk_forward_oof_calibrated": wf["oof_calibrated"],
            "sha256": hashlib.sha256((d / "model.joblib").read_bytes()).hexdigest(), "split_sha256": load_split(symbol)["sha256"]}
    (d / "meta.json").write_text(json.dumps(meta, indent=1, default=float), encoding="utf8")
    log(f"{tf}: challenger registered {version}")
    return version


def promote(symbol: str, version: str, approve: bool = False) -> dict:
    """Champion pointer: changes ONLY with explicit approval, and only for a model whose validation result passed the gate."""
    d = models_dir(symbol) / version
    meta = json.loads((d / "meta.json").read_text())
    val = meta.get("validation")
    problems = []
    if not approve:
        problems.append("explicit approval missing (--approve)")
    if not val:
        problems.append("no validation result yet (run ml-validate)")
    elif not val.get("passed_gate"):
        problems.append(f"validation gate not passed: {val.get('gate_failures')}")
    if problems:
        return {"promoted": False, "problems": problems}
    champ = models_dir(symbol) / f"champion_{meta['tf']}.json"
    history = json.loads(champ.read_text())["history"] if champ.exists() else []
    history.append({"version": version, "promoted": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    champ.write_text(json.dumps({"version": version, "history": history}, indent=1), encoding="utf8")
    return {"promoted": True, "version": version}


GATE = {"min_n": 1000, "min_selected_trades": 100, "brier_skill_gt": 0.0, "ece_le": 0.05}


def validate_model(symbol: str, version: str, log=print) -> dict:
    """The frozen challenger on the validation segment (once): metrics, calibration and the promotion gate."""
    from app.gold_research.study import out_dir
    d = models_dir(symbol) / version
    bundle = joblib.load(d / "model.joblib")
    meta = json.loads((d / "meta.json").read_text())
    tf = bundle["tf"]
    split = load_split(symbol)
    seg0 = int(datetime.fromisoformat(split["train"]["end_exclusive"]).timestamp())
    tr = dataset(pl.read_parquet(out_dir(symbol) / f"trades_{tf}_validation.parquet")).sort("entry_ts")
    tr = tr.filter(pl.col("entry_ts") >= seg0)
    evp = out_dir(symbol) / f"events_{tf}_validation.parquet"
    prior = pl.read_parquet(out_dir(symbol) / f"trades_{tf}_train.parquet")
    X = build_features(symbol, tf, "validation", tr, pl.read_parquet(evp) if evp.exists() else None, prior_trades=prior)
    X = X.select(bundle["features"])
    A, _ = _prep(X, bundle["kind"], bundle["scaler"])
    p_raw = bundle["model"].predict_proba(A)[:, 1]
    p = bundle["calibrator"].predict(p_raw)
    lab = labels(tr)
    m = metrics(lab[f"y_{PRIMARY_K:g}R"], p, lab["r2"])
    fails = []
    if m["n"] < GATE["min_n"]:
        fails.append("too few validation rows")
    if not (m.get("brier_skill", -1) > GATE["brier_skill_gt"]):
        fails.append("no Brier skill over the base rate")
    if not (m.get("ece", 1) <= GATE["ece_le"]):
        fails.append("calibration error too large")
    top = m["selection"].get("p>=0.5") or m["selection"].get("top_decile")
    if not top or top.get("n_trades", 0) < GATE["min_selected_trades"] or not ((top.get("expectancy_r_ci_low") or -1) > 0):
        fails.append("selected trades not profitable with confidence")
    meta["validation"] = {"run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "metrics": m, "gate": GATE,
                          "passed_gate": not fails, "gate_failures": fails}
    (d / "meta.json").write_text(json.dumps(meta, indent=1, default=float), encoding="utf8")
    log(f"{version}: validation {'PASSED' if not fails else 'did not pass'} the gate {fails}")
    return meta["validation"]
