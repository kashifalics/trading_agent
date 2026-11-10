"""Experiment-3 runner (docs/research/EXPERIMENT_3_PLAN.md, route 1). Analysis only; reads the TRAINING period only.

    python -m app.gold_research.exp3 gate       counts only (no outcomes): which tests have >= N_MIN development fills -> pre-registration
    python -m app.gold_research.exp3 simulate   setup trades and the control pool (H1, H4)
    python -m app.gold_research.exp3 develop    the pre-registered tests, pass criteria -> frozen candidate list
    python -m app.gold_research.exp3 report     docs/reports/XAUUSD_EXPERIMENT3.md

Execution, costs, controls and statistics are those of experiment 2 (limit at the signal close, live 20 candles, conservative fill,
bid/ask, stop = far edge + 0.1 ATR, 2R target, time stop, financing, matched controls of the same direction). Differences: H1/H4,
long and short pooled per test, fixes F1-F5, a power gate fixed before any outcome, and the halves criterion.
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.feature_engineering.indicators import atr as atr_fn
from app.gold_research import controls as C
from app.gold_research import sim
from app.gold_research import stats as Stt
from app.gold_research.combos import tf_state
from app.gold_research.events import ATR_PERIOD, bars_from_frame
from app.gold_research.exp2 import data as D2
from app.gold_research.exp2 import financing as F
from app.gold_research.exp2 import run as R2
from app.gold_research.exp3 import data as D
from app.gold_research.exp3 import setups as SU
from app.historical.config import DATA_ROOT, REPO_ROOT, TF_SECONDS
from app.historical.split import SPLIT_DIR
from app.historical.store import load_m1, load_tf
from app.historical.sync import bar_close
from app.patterns.context import compute_levels

TFS = SU.TFS
HOLDS = {"H1": (24, 48, 96), "H4": (30, 60, 120)}
PRIMARY_HOLD = {"H1": 48, "H4": 60}
TARGETS = (1.5, 2.0, 3.0)
PRIMARY_TARGET = 2.0
WAIT = 20
BUFFER_ATR = 0.1
N_MIN = 1000
FDR_Q, ALPHA = 0.10, 0.05
CONTROL_BARS = 20_000


def out_dir(symbol: str):
    return DATA_ROOT / "research" / symbol / "exp3"


def preregistration_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp3_preregistration.json"


def candidates_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp3_candidates.json"


def report_path(symbol: str):
    return REPO_ROOT / "docs" / "reports" / f"{symbol}_EXPERIMENT3.md"


def _sha(doc: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in doc.items() if k != "sha256"}, sort_keys=True).encode()).hexdigest()


def _git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:  # noqa: BLE001 - provenance only
        return None


# ------------------------------------------------------------------ inputs
def load_inputs(symbol: str, tf: str) -> dict:
    df = load_tf(symbol, tf, upto="train").sort("ts")
    S = sim.Series.from_frame(df, tf, load_m1(symbol, upto="train"))
    b = bars_from_frame(df, TF_SECONDS[tf])
    a = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    lv = compute_levels(df["ts"], bar_close(tf, b.t), b.h, b.l)
    d1 = tf_state(symbol, "D1", "train")
    j = np.searchsorted(d1["close"], bar_close(tf, b.t), side="right") - 1  # D1 candles closed by this candle's close only
    htf = np.where(j >= 0, d1["trend"][np.maximum(j, 0)], 0)
    orders = SU.setup_orders(b, a, lv, htf, tf)
    return {"df": df, "S": S, "b": b, "a": a, "orders": orders}


# ------------------------------------------------------------------ power gate (counts only)
def gate_counts(S: sim.Series, orders: pl.DataFrame, a: np.ndarray, tf: str, dev_start: int, dev_end: int) -> dict:
    """Orders and candle-level conservative fills per (setup) in the development period. Uses the same touch/cancel rule as the
    simulator; reads no outcome (no stop, target or P&L)."""
    idx = orders["idx"].to_numpy()
    if len(idx) == 0:
        return {}
    d = orders["direction"].to_numpy().astype(np.int64)
    lim, far = orders["limit"].to_numpy(), orders["far"].to_numpy()
    through = (S.ao - S.bo)[idx]
    J = idx[:, None] + 1 + np.arange(WAIT)
    real = J < S.n
    Jc = np.clip(J, 0, S.n - 1)
    Ld = (d > 0)[:, None]
    touch = np.where(Ld, S.al[Jc] < (lim - through)[:, None], S.bh[Jc] > (lim + through)[:, None]) & real
    cancel = np.where(Ld, S.bc[Jc] < far[:, None], S.bc[Jc] > far[:, None]) & real
    ft = np.where(touch.any(1), touch.argmax(1), WAIT)
    fc = np.where(cancel.any(1), cancel.argmax(1), WAIT)
    filled = (ft < WAIT) & (ft <= fc)
    room = idx + 1 + WAIT + max(HOLDS[tf]) < S.n  # the time stop can still end inside the loaded period
    in_dev = (S.t[idx] >= dev_start) & (S.t[idx] < dev_end) & room
    out = {}
    for setup in orders["setup"].unique().sort().to_list():
        m = (orders["setup"] == setup).to_numpy() & in_dev
        out[setup] = {"orders": int(m.sum()), "est_fills": int((m & filled).sum()), "long": int((m & filled & (d > 0)).sum()),
                      "short": int((m & filled & (d < 0)).sum())}
    return out


def gate(symbol: str, log=print, inputs: dict | None = None) -> dict:
    """Fix the test list from counts only and write the pre-registration (refuses to overwrite one that exists)."""
    p = preregistration_path(symbol)
    if p.exists():
        log(f"{p.name} already exists: not overwritten")
        return json.loads(p.read_text())
    sp = D.freeze_split(symbol)
    lo, hi = D.epoch(sp["development"]["start"]), D.epoch(sp["development"]["end_exclusive"])
    counts = {}
    for tf in TFS:
        x = (inputs or {}).get(tf) or load_inputs(symbol, tf)
        counts[tf] = gate_counts(x["S"], x["orders"], x["a"], tf, lo, hi)
        log(f"{tf}: counted " + ", ".join(f"{k} {v['est_fills']}" for k, v in counts[tf].items()))
    tests = []
    for setup, tf in SU.TESTS:
        c = counts[tf].get(setup, {"orders": 0, "est_fills": 0, "long": 0, "short": 0})
        tests.append({"setup": setup, "tf": tf, **c, "status": "run" if c["est_fills"] >= N_MIN else "not testable (fewer fills than N_MIN)"})
    doc = {"symbol": symbol, "experiment": 3, "plan": "docs/research/EXPERIMENT_3_PLAN.md", "route": sp["route"],
           "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code_commit": _git_head(),
           "split_sha256": sp["sha256"], "n_min": N_MIN, "counts_note": "candle-level conservative fills in development; no outcome read",
           "tests": tests, "setups": SU.SETUPS,
           "main_setting": {"target_r": PRIMARY_TARGET, "holds": PRIMARY_HOLD, "wait": WAIT, "stop": f"far edge + {BUFFER_ATR} ATR",
                            "fill": "conservative (trade through by the spread)", "financing": "fixed $0.10/oz/night",
                            "directions": "long and short pooled; controls matched on direction"},
           "criteria": ["Benjamini-Hochberg q < 0.10 over the tests run, edge > 0", "mean R > 0 with p < 0.05 (main costs)",
                        "mean R > 0 with $0.10 slippage per side", "mean R > 0 with 1.5x spread",
                        "deflated Sharpe > 0.95 counting all trials of experiments 1-3", "positive in >= 60% of development years",
                        "positive in both halves (before / from 2012-01-01)", f">= {N_MIN} development trades"]}
    doc["sha256"] = _sha(doc)
    p.write_text(json.dumps(doc, indent=1), encoding="utf8")
    log(f"pre-registration written: {p} ({sum(t['status'] == 'run' for t in tests)} of {len(tests)} tests run)")
    return doc


def load_preregistration(symbol: str) -> dict:
    p = preregistration_path(symbol)
    if not p.exists():
        raise RuntimeError("no experiment-3 pre-registration: run the gate and commit it before any outcome is computed")
    d = json.loads(p.read_text())
    if _sha(d) != d["sha256"]:
        raise RuntimeError("experiment-3 pre-registration was edited after it was written")
    return d


# ------------------------------------------------------------------ simulation (experiment-2 mechanics, experiment-3 holds)
def simulate_orders(S, a, d, idx, limit, far, tf, gs, roll, fred) -> dict:
    through = (S.ao - S.bo)[idx]
    o = sim.Orders(d=d.astype(np.int64), entry_bar=idx + 1, stop=far - d * BUFFER_ATR * a[idx], atr=a[idx], limit=limit, cancel=far,
                   wait=WAIT, through=through)
    res = sim.simulate(S, o, holds=HOLDS[tf], hit_targets=TARGETS)
    out = {"simulated": res["simulated"], "fill_ts": res["fill_ts"], "fill_bar": res["fill_bar"], "risk_px": res["risk_px"],
           "entry_px": res["entry_px"], "spread_signal": through}
    step = TF_SECONDS[tf]
    for k in TARGETS:
        for h in HOLDS[tf]:
            r = sim.r_multiple(res, k, h)
            hit, reached, stopped = res[f"hit_{k:g}"], res[f"mfe_{h}"] >= k, res[f"stopped_{h}"]
            end_bar = res["fill_bar"] + h - 1
            exit_ts = np.where(reached, S.t[np.clip(hit, 0, S.n - 1)] + step,
                               np.where(stopped, res["stop_ts"], S.t[np.clip(end_bar, 0, S.n - 1)] + step))
            key, ok = f"{k:g}R_{h}", res["simulated"]
            out[f"r_{key}"] = np.where(ok, r, np.nan)
            out[f"exit_{key}"] = np.where(ok, exit_ts, -1)
            out[f"gap_{key}"] = ok & D2.gap_between(gs, res["fill_ts"], exit_ts)
            for sc in F.SCENARIOS:
                cst = F.cost_usd_per_oz(sc, d, res["fill_ts"], exit_ts, res["entry_px"], roll, fred)
                out[f"fin_{sc}_{key}"] = None if cst is None else cst / res["risk_px"]
    return out


def run_tf(symbol: str, tf: str, log=print, inputs: dict | None = None) -> None:
    load_preregistration(symbol)  # outcomes are computed only after the test list is fixed
    sp = D.load(symbol)
    x = inputs or load_inputs(symbol, tf)
    df, S, a, orders = x["df"], x["S"], x["a"], x["orders"]
    gs = D.unscheduled_starts(symbol, sp["development"]["start"], sp["development"]["end_exclusive"])
    years = df["ts"].dt.year()
    roll = F.rollovers(int(years.min()), int(years.max()) + 1)
    fred = F.load_fred()
    idx = orders["idx"].to_numpy()
    d = orders["direction"].to_numpy().astype(np.int64)
    so = simulate_orders(S, a, d, idx, orders["limit"].to_numpy(), orders["far"].to_numpy(), tf, gs, roll, fred)
    vol = C.vol_bucket(a)
    dist = d * (S.bc[idx] - orders["limit"].to_numpy()) / a[idx]
    width = np.abs(orders["limit"].to_numpy() - orders["far"].to_numpy()) / a[idx]
    trades = R2._frame(so, {"setup": orders["setup"], "direction": orders["direction"], "idx": orders["idx"],
                            "signal_ts": pl.Series(S.t[idx]), "dist_b": pl.Series(C.bucket(dist, C.DIST_EDGES).astype(np.int8)),
                            "width_b": pl.Series(C.bucket(width, C.WIDTH_EDGES).astype(np.int8)), "vol": pl.Series(vol[idx])})
    trades = trades.filter(pl.col("simulated"))
    trades = trades.with_columns(session=pl.Series(C.session_ny(trades["fill_ts"].to_numpy())))
    rng = np.random.default_rng(sum(map(ord, f"exp3{symbol}{tf}")))
    elig = np.flatnonzero(np.isfinite(a) & (np.arange(S.n) + max(HOLDS[tf]) + WAIT + 2 < S.n))
    bars = np.sort(rng.choice(elig, min(len(elig), CONTROL_BARS), replace=False))
    frames = []
    for dd in (1, -1):
        for i_, dc in enumerate(C.DIST_CENTRES):
            for j_, wc in enumerate(C.WIDTH_CENTRES):
                lim = S.bc[bars] - dd * dc * a[bars]
                far = lim - dd * wc * a[bars]
                co = simulate_orders(S, a, np.full(len(bars), dd), bars, lim, far, tf, gs, roll, fred)
                frames.append(R2._frame(co, {"direction": pl.Series(np.full(len(bars), dd, np.int8)), "signal_ts": pl.Series(S.t[bars]),
                                             "dist_b": pl.Series(np.full(len(bars), i_, np.int8)),
                                             "width_b": pl.Series(np.full(len(bars), j_, np.int8)), "vol": pl.Series(vol[bars])}
                                        ).filter(pl.col("simulated")))
    pool = pl.concat(frames)
    pool = pool.with_columns(session=pl.Series(C.session_ny(pool["fill_ts"].to_numpy())))
    o = out_dir(symbol)
    o.mkdir(parents=True, exist_ok=True)
    trades.write_parquet(o / f"trades_{tf}.parquet", compression="zstd")
    pool.write_parquet(o / f"pool_{tf}.parquet", compression="zstd")
    log(f"{tf}: {trades.height:,} filled setup trades, {pool.height:,} filled control trades")


# ------------------------------------------------------------------ development statistics
def development_frame(df: pl.DataFrame, key: str, symbol: str) -> pl.DataFrame:
    sp = D.load(symbol)
    lo, hi = D.epoch(sp["development"]["start"]), D.epoch(sp["development"]["end_exclusive"])
    ok = (pl.col("fill_ts") >= lo) & (pl.col(f"exit_{key}") < hi) & ~pl.col(f"gap_{key}") & pl.col(f"r_{key}").is_not_nan()
    year = (pl.col("fill_ts") * 1_000_000).cast(pl.Datetime("us")).dt.year()
    return df.filter(ok).with_columns(period=pl.concat_str([year.cast(pl.Utf8), pl.lit(":development")]), year=year,
                                      segment=pl.lit("development"), entry=pl.lit("limit"), risk_b=pl.lit(-1, pl.Int8),
                                      entry_ts=pl.col("fill_ts"))


def prior_trials(symbol: str) -> tuple[dict, list[float]]:
    """Sample-size terms (1/T) of every earlier trial: experiment 1 (stages 1-3) and experiment 2's 36 pre-registered tests."""
    n1, v1 = R2._prior_null_var(symbol)
    inv = [v1] * n1
    counts = dict(R2.PRIOR_TRIALS)
    p2 = R2.out_dir(symbol) / "development.json"
    if p2.exists():
        rows = json.loads(p2.read_text())["rows"]
        inv += [1.0 / max(r["trades"], 2) for r in rows]
        counts["experiment 2"] = len(rows)
    return counts, inv


def develop(symbol: str, log=print) -> dict:
    pre = load_preregistration(symbol)
    run_tests = [t for t in pre["tests"] if t["status"] == "run"]
    rows = []
    for t in run_tests:
        tf, setup, h = t["tf"], t["setup"], PRIMARY_HOLD[t["tf"]]
        key = f"{PRIMARY_TARGET:g}R_{h}"
        o = out_dir(symbol)
        tr, pool = pl.read_parquet(o / f"trades_{tf}.parquet"), pl.read_parquet(o / f"pool_{tf}.parquet")
        g = development_frame(tr, key, symbol).filter(pl.col("setup") == setup)
        dev_p = development_frame(pool, key, symbol)
        row = {"tf": tf, "setup": setup, "trades": g.height, "long": int((g["direction"] > 0).sum()), "short": int((g["direction"] < 0).sum())}
        if g.height:
            e = R2.evaluate(g, dev_p, key, tf, h)
            fr = e.pop("_frame")
            row["main"] = e
            cl = Stt.cluster_ids(fr["entry_ts"].to_numpy(), h * TF_SECONDS[tf])
            row["stress"] = {}
            for name, kw in (("slippage_0.10", {"slip": 0.10}), ("spread_x1.5", {"spread_x": 1.5}), ("no_financing", {"scenario": "none"}),
                             ("fred_proxy", {"scenario": "fred_proxy"})):
                v = R2.net_r(g, key, **kw)
                row["stress"][name] = None if v is None else Stt.clustered_mean(v[np.isfinite(v)], cl[np.isfinite(v)])
            yr = fr.group_by("year").agg(pl.col("r").mean().alias("m"), pl.len().alias("n")).sort("year")
            row["years"] = yr.rows()
            row["share_positive_years"] = float((yr["m"] > 0).mean()) if yr.height else 0.0
            halves = fr.with_columns(half=pl.when(pl.col("year") < 2012).then(pl.lit("2003-2011")).otherwise(pl.lit("2012-2020")))
            row["halves"] = {k: float(v) for k, v in halves.group_by("half").agg(pl.col("r").mean()).iter_rows()}
            row["_r"] = fr["r"].to_numpy().tolist()
            row["grid"] = {f"{k:g}R_{hh}": float(np.nanmean(R2.net_r(g, f'{k:g}R_{hh}'))) for k in TARGETS for hh in HOLDS[tf]}
        rows.append(row)
        log(f"{tf} {setup}: {g.height:,} development trades")
    tested = [r for r in rows if r.get("main") and np.isfinite(r["main"].get("edge_se", np.nan))]
    for r, q in zip(tested, Stt.bh(np.array([r["main"]["p_edge"] for r in tested]))):
        r["q"] = float(q)
    counts, inv = prior_trials(symbol)  # tests the gate ruled "not testable" were never run, so they are not trials
    n_trials = len(inv) + len(rows)
    null_var = float(np.mean(inv + [1.0 / max(r["trades"], 2) for r in rows]))
    for r in rows:
        r["dsr"] = R2.deflated_sharpe(np.array(r.pop("_r", [])), n_trials, null_var) if r.get("main") else float("nan")
        crit = {}
        if "q" in r:
            m, st = r["main"], r["stress"]
            crit = {"bh_q_lt_0.10_and_edge_positive": r["q"] < FDR_Q and m["edge"] > 0,
                    "profitable_main": m["mean_r"] > 0 and m["p_profit"] < ALPHA,
                    "profitable_slippage_0.10": st["slippage_0.10"]["mean"] > 0, "profitable_spread_x1.5": st["spread_x1.5"]["mean"] > 0,
                    "deflated_sharpe_gt_0.95": r["dsr"] > 0.95, "positive_years_ge_60pct": r["share_positive_years"] >= 0.60,
                    "positive_both_halves": len(r["halves"]) == 2 and all(v > 0 for v in r["halves"].values()),
                    f"trades_ge_{N_MIN}": r["trades"] >= N_MIN}
        r["criteria"] = crit
        r["status"] = ("no trades" if "q" not in r else "CANDIDATE" if all(crit.values()) else
                       "no: " + ", ".join(k for k, v in crit.items() if not v))
    cands = [{"tf": r["tf"], "setup": r["setup"]} for r in rows if r["status"] == "CANDIDATE"]
    summary = {"symbol": symbol, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "segment": "development: whole training period", "preregistration_sha256": pre["sha256"],
               "pre_registered_tests": len(pre["tests"]), "tests_run": len(rows), "trials_counted_for_deflated_sharpe": n_trials,
               "prior_trials": counts, "fred": F.fred_status(), "candidates": cands, "rows": rows,
               "not_testable": [t for t in pre["tests"] if t["status"] != "run"]}
    o = out_dir(symbol)
    o.mkdir(parents=True, exist_ok=True)
    (o / "development.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf8")
    p = candidates_path(symbol)
    if not p.exists():
        doc = {"symbol": symbol, "created": summary["generated"], "candidates": cands, "preregistration_sha256": pre["sha256"],
               "main_setting": pre["main_setting"]}
        doc["sha256"] = _sha(doc)
        p.write_text(json.dumps(doc, indent=1), encoding="utf8")
    else:
        log(f"{p.name} already frozen: not overwritten")
    return summary


def verify_scope(symbol: str) -> dict:
    """Evidence that nothing at or after the training end was used."""
    end = D.epoch(D.load(symbol)["development"]["end_exclusive"])
    out = {}
    for p in sorted(out_dir(symbol).glob("*.parquet")):
        df = pl.read_parquet(p, columns=["signal_ts", "fill_ts"])
        out[p.name] = {"rows": df.height, "max_signal_before_training_end": bool(df["signal_ts"].max() < end) if df.height else True,
                       "max_fill_before_training_end": bool(df["fill_ts"].max() < end) if df.height else True}
    return out
