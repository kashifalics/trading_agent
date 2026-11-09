"""Final technical and statistical audit of the gold research pipeline (requested before any new experiment). Analysis only.

Executable checks, not code reading:
  splits        fractions, Saturday boundaries, no overlap
  purging       every stored trade's outcome window lies inside its own segment
  folds         the model walk-forward folds never train on rows whose outcome reaches the test block
  truncation    model features computed on history cut at T equal those computed on the full training history (rows before T)
  mt_reference  BH and Holm re-implemented independently and compared on the real stage-1 p-values
  calibration   training out-of-fold reliability curves (cross-fitted isotonic) for the H1 and H4 champions-in-waiting
  null          the whole pipeline on REAL training M1 with every minute's move given a random sign (H1, H4): how many false
                candidates and how uniform the p-values are
  h4            why H4 is closest to break-even: cost decomposition per timeframe and holding-period grid (training trades only)
Reads training files and the candles of the training period only (plus validation trade TIMESTAMPS for the purging check, never
their outcomes). Never reads the sealed final-test period, changes no split, model or file outside data/historical/research/audit2.
"""
import json
from datetime import datetime, timezone

import numpy as np
import polars as pl
from scipy import stats

from app.gold_research import ml, sim, study
from app.gold_research import stats as Stt
from app.historical.config import CLEAN, TF_SECONDS
from app.historical.split import load_split
from app.historical.store import load_tf as real_load_tf


def _ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp())


def check_splits(symbol: str) -> dict:
    s = load_split(symbol)
    tot = s["m1_rows_total"]
    b1, b2 = datetime.fromisoformat(s["train"]["end_exclusive"]), datetime.fromisoformat(s["validation"]["end_exclusive"])
    return {"train_share": s["train"]["m1_rows"] / tot, "validation_share": s["validation"]["m1_rows"] / tot,
            "test_share": s["test"]["m1_rows_when_frozen"] / tot, "boundaries_are_saturday_midnight": b1.weekday() == 5 and b2.weekday() == 5
            and b1.hour == 0 and b2.hour == 0, "ordered": s["train"]["start"] < s["train"]["end_exclusive"] <= s["validation"]["start"]
            < s["validation"]["end_exclusive"] <= s["test"]["start"], "sha256": s["sha256"]}


def check_purging(symbol: str) -> dict:
    s = load_split(symbol)
    t_end, v_end = _ts(s["train"]["end_exclusive"]), _ts(s["validation"]["end_exclusive"])
    out = {}
    o = study.out_dir(symbol)
    for seg, lo, hi in (("train", 0, t_end), ("validation", t_end, v_end)):
        for p in sorted(o.glob(f"trades_*_{seg}.parquet")):
            tf = p.stem.split("_")[-2]
            e = pl.read_parquet(p, columns=["entry_ts", "signal_ts", "segment"])
            if e.height == 0:
                out[p.stem] = {"rows": 0}
                continue
            end = e["entry_ts"].to_numpy() + sim.HMAX * TF_SECONDS[tf]
            out[p.stem] = {"rows": e.height, "first_entry_inside": bool(e["entry_ts"].min() >= lo),
                           "outcome_windows_inside_segment_upper_bound": bool(end.max() <= hi + 3 * 86400),
                           "latest_window_end": datetime.fromtimestamp(int(end.max()), timezone.utc).isoformat(),
                           "segment_labels": sorted(set(e["segment"].to_list()))}
    return out


def check_folds(symbol: str, tf: str) -> dict:
    tr = ml.dataset(pl.read_parquet(study.out_dir(symbol) / f"trades_{tf}_train.parquet")).sort("entry_ts")
    ts = tr["entry_ts"].to_numpy()
    hold = ml.HOLD * TF_SECONDS[tf]
    folds = []
    for rolling in (False, True):
        for train, test, (t0, t1) in ml.purged_folds(ts, hold, rolling=rolling):
            folds.append({"rolling": rolling, "n_train": int(len(train)), "n_test": int(len(test)),
                          "train_outcomes_end_before_test": bool((ts[train] + hold < t0).all()),
                          "train_strictly_before_test": bool(ts[train].max() < t0), "test_start": datetime.fromtimestamp(t0, timezone.utc).date().isoformat()})
    return {"tf": tf, "rows": tr.height, "folds": folds, "all_ok": all(f["train_outcomes_end_before_test"] for f in folds)}


def check_feature_truncation(symbol: str, tf: str, cut_iso: str = "2012-01-02T00:00:00+00:00") -> dict:
    """Features of training rows signalled before T must not change when every candle after T is removed."""
    from app.gold_research import combos
    T = _ts(cut_iso)
    o = study.out_dir(symbol)
    tr = ml.dataset(pl.read_parquet(o / f"trades_{tf}_train.parquet")).sort("entry_ts")
    ev = pl.read_parquet(o / f"events_{tf}_train.parquet")
    full = ml.build_features(symbol, tf, "train", tr, ev)

    def cut_loader(symbol_, tf_, upto="train", final_test=False):
        df = real_load_tf(symbol_, tf_, upto=upto, final_test=final_test)
        from app.historical.sync import bar_close, epoch
        return df.filter(pl.Series(bar_close(tf_, epoch(df["ts"])) <= T))

    keep = (tr["signal_ts"] + TF_SECONDS[tf] <= T) & (tr["entry_ts"] < T)
    sub = tr.filter(keep)
    old_ml, old_c = ml.load_tf, combos.load_tf
    ml.load_tf, combos.load_tf = cut_loader, cut_loader
    try:
        n_cut = cut_loader(symbol, tf).height
        cut = ml.build_features(symbol, tf, "train", sub, ev.filter(pl.col("idx") < n_cut))
    finally:
        ml.load_tf, combos.load_tf = old_ml, old_c
    a = full.filter(keep)
    diffs = {}
    for c in a.columns:
        x, y = a[c].to_numpy().astype(float), cut[c].to_numpy().astype(float)
        same = np.isclose(x, y, equal_nan=True, rtol=0, atol=1e-9)
        if not same.all():
            diffs[c] = {"rows_different": int((~same).sum()), "max_abs_diff": float(np.nanmax(np.abs(x - y)))}
    return {"tf": tf, "cut": cut_iso, "rows_compared": a.height, "features": a.width, "features_different": diffs}


def _bh_ref(p: np.ndarray) -> np.ndarray:
    m = len(p)
    o = np.argsort(p)
    q = p[o] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(m)
    out[o] = np.minimum(q, 1)
    return out


def _holm_ref(p: np.ndarray) -> np.ndarray:
    m = len(p)
    o = np.argsort(p)
    adj = np.maximum.accumulate(p[o] * (m - np.arange(m)))
    out = np.empty(m)
    out[o] = np.minimum(adj, 1)
    return out


def check_multiple_testing(symbol: str) -> dict:
    d = json.loads((study.out_dir(symbol) / "discovery_stage1.json").read_text())
    rows = [r for r in d["rows"] if "q" in r]
    p = np.array([r["primary"]["p_edge"] for r in rows])
    q_stored = np.array([r["q"] for r in rows])
    rng = np.random.default_rng(1)
    pr = rng.uniform(0, 1, 5000)
    out = {"tests": len(p), "bh_max_abs_diff_vs_reference": float(np.max(np.abs(Stt.bh(p) - _bh_ref(p)))),
           "bh_stored_q_max_abs_diff": float(np.max(np.abs(q_stored - _bh_ref(p)))),
           "holm_max_abs_diff_vs_reference": float(np.max(np.abs(Stt.holm(p) - _holm_ref(p)))),
           "bh_random_max_abs_diff": float(np.max(np.abs(Stt.bh(pr) - _bh_ref(pr)))),
           "candidates_recounted": int((_bh_ref(p) < study.FDR_Q).sum() - sum(1 for r in rows if r["q"] < study.FDR_Q and r["primary"]["edge"] <= 0)),
           "one_sided_test": "H1: edge > 0; p from a t distribution with (clusters - 1) df on week/hold-clustered standard errors"}
    pv = json.loads((study.out_dir(symbol) / "validation.json").read_text())
    vp = np.array([r["validation"]["p_edge"] for r in pv["rows"] if r["validation"].get("n", 0) >= study.MIN_N])
    vh = np.array([r["holm_p"] for r in pv["rows"] if r["validation"].get("n", 0) >= study.MIN_N])
    out["validation_holm_max_abs_diff_vs_reference"] = float(np.max(np.abs(_holm_ref(vp) - vh))) if len(vp) else None
    return out


def calibration_curves(symbol: str, tf: str, kind: str) -> dict:
    """Training-only: cross-fitted out-of-fold probabilities of the selected model type, binned."""
    from app.ml_engine.evaluation import calibration_curve
    tr = ml.dataset(pl.read_parquet(study.out_dir(symbol) / f"trades_{tf}_train.parquet")).sort("entry_ts")
    if tr.height > ml.ML_MAX_ROWS:
        tr = tr.gather_every(int(np.ceil(tr.height / ml.ML_MAX_ROWS)))
    X = ml.build_features(symbol, tf, "train", tr, pl.read_parquet(study.out_dir(symbol) / f"events_{tf}_train.parquet"))
    lab = ml.labels(tr)
    y = lab[f"y_{ml.PRIMARY_K:g}R"]
    wf = ml.walk_forward(X, y, lab["r2"], tr["entry_ts"].to_numpy(), ml.HOLD * TF_SECONDS[tf], kind, nested=(kind == "lgbm"))
    p_raw, p_cal = wf["_oof"], None
    from sklearn.isotonic import IsotonicRegression
    ts = tr["entry_ts"].to_numpy()
    p_cal = np.full(len(y), np.nan)
    for _train, test, (t0, _t1) in ml.purged_folds(ts, ml.HOLD * TF_SECONDS[tf]):
        e = np.flatnonzero(np.isfinite(p_raw) & (ts < t0))
        if len(e) >= 1000:
            p_cal[test] = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(p_raw[e], y[e]).predict(p_raw[test])
    ok = np.isfinite(p_cal)
    cc = calibration_curve(p_cal[ok], y[ok])
    return {"tf": tf, "kind": kind, "rows": int(ok.sum()), "base_rate": float(y[ok].mean()), "mean_predicted": float(p_cal[ok].mean()),
            "ece": cc["ece"], "bins": cc["bins"], "brier_skill": wf["oof_calibrated"].get("brier_skill")}


def sign_flip_null(symbol: str, tfs=("H1", "H4"), seed: int = 11, log=print) -> dict:
    """Real training M1 with each minute's move randomly signed (volatility, sessions, gaps kept; direction destroyed); the whole
    pipeline (detectors, simulator, controls, discovery statistics) in a scratch folder. Expected: ~0 candidates, uniform p-values."""
    import tempfile
    from pathlib import Path

    from app.gold_research import nulls
    from app.historical import split as Sp
    from app.historical import store as Sto
    from app.historical.build import build_timeframes, resample
    t_end = load_split(symbol)["train"]["end_exclusive"]
    files = sorted((CLEAN / symbol / "M1").glob("*.parquet"))
    cols = ["ts", *[f"{s}_{k}" for s in ("bid", "ask") for k in ("open", "high", "low", "close")], "bid_volume", "ask_volume"]
    m1 = pl.concat([pl.read_parquet(f, columns=cols) for f in files if int(f.stem) <= int(t_end[:4])]).filter(
        pl.col("ts") < datetime.fromisoformat(t_end)).sort("ts")
    flipped = nulls.sign_flip(m1, seed=seed)
    tmp = Path(tempfile.mkdtemp(prefix="signflip_"))
    saved = {}
    patches = [(Sto, ("CLEAN", "DATA_ROOT", "SPLIT_DIR")), (Sp, ("CLEAN", "SPLIT_DIR", "REPORTS")), (study, ("CLEAN", "DATA_ROOT", "SPLIT_DIR"))]
    try:
        for mod, names in patches:
            for nm in names:
                saved[(mod, nm)] = getattr(mod, nm)
                setattr(mod, nm, tmp / ("docs" if nm == "SPLIT_DIR" else "clean" if nm == "CLEAN" else "reports" if nm == "REPORTS" else "root"))
        (tmp / "clean" / symbol / "M1").mkdir(parents=True)
        flipped.write_parquet(tmp / "clean" / symbol / "M1" / "all_years.parquet")
        for tf, df in build_timeframes(resample(flipped, "5m")).items():
            (tmp / "clean" / symbol / tf).mkdir(parents=True)
            df.write_parquet(tmp / "clean" / symbol / tf / "all.parquet")
        Sp.freeze_split(symbol, log=lambda m: None)
        Sto.build_m1_store(symbol, log=lambda m: None)
        for tf in tfs:
            log(f"sign-flip null: {tf}")
            study.run_timeframe(symbol, tf, "train")
        s = study.discover(symbol, list(tfs), log=lambda m: None)
    finally:
        for (mod, nm), v in saved.items():
            setattr(mod, nm, v)
    rows = [r for r in s["rows"] if "q" in r]
    p = np.array([r["primary"]["p_edge"] for r in rows])
    edges = np.array([r["primary"]["edge"] for r in rows])
    pp = np.array([r["primary"]["p_profit"] for r in rows])
    return {"tfs": list(tfs), "training_span": f"{m1['ts'].min()} to {m1['ts'].max()} (the null's own first 70%)", "tests": len(rows),
            "candidates": len(s["candidates"]), "candidate_list": s["candidates"], "share_p_below_0_05": float((p < 0.05).mean()),
            "ks_uniform_p": float(stats.kstest(p, "uniform").pvalue), "mean_edge": float(edges.mean()), "median_abs_edge": float(np.median(np.abs(edges))),
            "share_profit_p_below_0_05": float((pp < 0.05).mean()), "mean_r_all_tests": float(np.mean([r["primary"]["mean_r"] for r in rows]))}


def h4_diagnostics(symbol: str) -> dict:
    """Training trades only: net and gross (spread added back) R by timeframe and entry type, cost as a share of risk, and the
    main 2R target over every holding period."""
    out = {}
    for tf in study.STUDY_TFS:
        p = study.out_dir(symbol) / f"trades_{tf}_train.parquet"
        if not p.exists():
            continue
        tr = pl.read_parquet(p)
        r = study._r(tr, study.PRIMARY_TARGET, study.PRIMARY_HOLD)
        cost = tr["spread_entry"].to_numpy().astype(float) / tr["risk_px"].to_numpy()
        ok = np.isfinite(r) & np.isfinite(cost)
        ent = tr["entry"].to_numpy()
        res = {"trades": int(ok.sum()), "mean_r_net": float(r[ok].mean()), "mean_cost_r": float(cost[ok].mean()),
               "median_cost_r": float(np.median(cost[ok])), "mean_r_gross": float((r + cost)[ok].mean()),
               "median_risk_atr": float(np.median(tr["risk_atr"].to_numpy()[ok])), "median_risk_usd": float(np.median(tr["risk_px"].to_numpy()[ok]))}
        for e in ("market", "limit"):
            m = ok & (ent == e)
            if m.any():
                res[e] = {"trades": int(m.sum()), "mean_r_net": float(r[m].mean()), "mean_cost_r": float(cost[m].mean()),
                          "mean_r_gross": float((r + cost)[m].mean())}
        res["holds"] = {}
        for h in sim.HOLDS:
            rh = study._r(tr, study.PRIMARY_TARGET, h)
            m = np.isfinite(rh) & np.isfinite(cost)
            res["holds"][h] = {"mean_r_net": float(rh[m].mean()), "mean_r_gross": float((rh + cost)[m].mean()),
                               "share_ended_by_time": float(np.mean(~tr[f"stopped_{h}"].to_numpy()[m] & (tr[f"mfe_{h}"].to_numpy()[m] < study.PRIMARY_TARGET)))}
        out[tf] = res
    return out


def run(symbol: str = "XAUUSD", log=print, null: bool = True) -> dict:
    res = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    res["splits"] = check_splits(symbol)
    log("splits checked")
    res["purging"] = check_purging(symbol)
    log("purging checked")
    res["folds"] = {tf: check_folds(symbol, tf) for tf in ml.ML_TFS}
    log("folds checked")
    res["truncation"] = check_feature_truncation(symbol, "H4")
    log(f"feature truncation checked: {res['truncation']['features_different']}")
    res["multiple_testing"] = check_multiple_testing(symbol)
    log("multiple testing re-implemented")
    res["h4"] = h4_diagnostics(symbol)
    log("H4 diagnostics done")
    ml_summary = json.loads((study.out_dir(symbol) / "ml_training.json").read_text())
    res["calibration"] = {tf: calibration_curves(symbol, tf, ml_summary["tfs"][tf]["best_kind"]) for tf in ("H4", "H1")}
    log("calibration curves done")
    if null:
        res["sign_flip_null"] = sign_flip_null(symbol, log=log)
        log(f"sign-flip null: {res['sign_flip_null']['candidates']} candidates of {res['sign_flip_null']['tests']}")
    out = study.out_dir(symbol) / "pipeline_audit.json"
    out.write_text(json.dumps(res, indent=1, default=float), encoding="utf8")
    log(f"written: {out}")
    return res
