"""Experiment 4 (requested 2026-11-12): does the user's flexible double top / double bottom have an edge on gold? TRAINING period only.

    python -m app.gold_research.exp4 gate      counts only (no outcome) -> pre-registration (commit it before simulating)
    python -m app.gold_research.exp4 simulate  trades of every pre-registered timeframe (real bid/ask, 1-minute stop/target order)
    python -m app.gold_research.exp4 develop   statistics, pass criteria -> frozen result and docs/reports/XAUUSD_EXPERIMENT4.md

Main setting (fixed before any outcome): the detector exactly as pasted (lookback 20, tolerance 0.05%), market entry at the next
candle's open, stop beyond the structural extreme (the higher peak / lower bottom) + 0.1 ATR, 2R target, 48-candle time stop,
Dukascopy bid/ask. This is the pattern study's standard, so the result compares directly with the library's double top. The pasted
levels (stop 1.5 ATR beyond the peak, targets 2 and 4 ATR) are not tested: their first target is below 1:1 reward:risk by design.
Edge = R minus the matched random-entry control mean (study control pools of the same training period).
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.feature_engineering.indicators import atr as atr_fn
from app.gold_research import controls as C
from app.gold_research import sim, study
from app.gold_research import stats as Stt
from app.gold_research.events import ATR_PERIOD, bars_from_frame
from app.gold_research.exp2 import run as R2
from app.gold_research.exp3 import run as R3
from app.gold_research.exp4.detect import LOOKBACK, TOLERANCE, detect
from app.historical.config import DATA_ROOT, REPO_ROOT, TF_SECONDS
from app.historical.split import SPLIT_DIR, load_split
from app.historical.store import load_m1, load_tf

TFS = ("M5", "M15", "M30", "H1", "H4", "D1")
SIDES = {-1: "double top (short)", 1: "double bottom (long)"}
TARGET, HOLD = study.PRIMARY_TARGET, study.PRIMARY_HOLD  # 2R, 48 candles
N_MIN = study.MIN_N  # 100 trades
FDR_Q, ALPHA = 0.10, 0.05
BROKER_SPREAD = 0.30  # the user's round-trip gold spread, USD/oz
GRID_TARGETS, GRID_HOLDS = (1.0, 1.5, 2.0, 3.0), (24, 48, 96)  # description only


def out_dir(symbol: str):
    return DATA_ROOT / "research" / symbol / "exp4"


def preregistration_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp4_preregistration.json"


def result_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp4_result.json"


def report_path(symbol: str):
    return REPO_ROOT / "docs" / "reports" / f"{symbol}_EXPERIMENT4.md"


def _sha(doc: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in doc.items() if k != "sha256"}, sort_keys=True).encode()).hexdigest()


def _git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:  # noqa: BLE001 - provenance only
        return None


def signals(df: pl.DataFrame) -> pl.DataFrame:
    """Both sides' signals of one timeframe: idx, direction, structural level (bid candles, as the pasted code uses one series)."""
    h, lo, c = (df[k].to_numpy() for k in ("bid_high", "bid_low", "bid_close"))
    frames = []
    for d in SIDES:
        s = detect(h, lo, c, side=d)
        frames.append(pl.DataFrame({"idx": s["idx"], "direction": np.full(len(s["idx"]), d, np.int64), "stop_level": s["level"]}))
    return pl.concat(frames).sort("idx")


# ------------------------------------------------------------------ 1. power gate: counts only
def gate(symbol: str, log=print) -> dict:
    p = preregistration_path(symbol)
    if p.exists():
        log(f"{p.name} already exists: not overwritten")
        return json.loads(p.read_text())
    split = load_split(symbol)
    tests = []
    for tf in TFS:
        df = load_tf(symbol, tf, upto="train").sort("ts")
        sg = signals(df)
        room = (sg["idx"] + 1 + HOLD < df.height).to_numpy()
        for d, name in SIDES.items():
            n = int(((sg["direction"] == d).to_numpy() & room).sum())
            tests.append({"tf": tf, "direction": "short" if d < 0 else "long", "pattern": name, "signals": n,
                          "status": "run" if n >= N_MIN else f"not testable (fewer than {N_MIN} signals)"})
        log(f"{tf}: " + ", ".join(f"{t['pattern']} {t['signals']}" for t in tests if t["tf"] == tf))
    doc = {"symbol": symbol, "experiment": 4, "requested": "2026-11-12, user's pasted detect_flexible_double_top",
           "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code_commit": _git_head(),
           "split_sha256": split["sha256"], "segment": "train (2003-05-05 to 2020-02-08), already examined by experiments 1-3",
           "counts_note": "signals with room for the time stop; no outcome read", "tests": tests,
           "detector": {"lookback": LOOKBACK, "tolerance_pct": TOLERANCE, "min_tail": 5, "series": "bid OHLC",
                        "dedupe": "one signal per pair of peaks (first close through the neckline)", "mirror": "double bottom"},
           "main_setting": {"entry": "market, next candle's open (ask to buy, bid to sell)",
                            "stop": f"structural extreme + {study.STOP_BUFFER_ATR} ATR({ATR_PERIOD})", "target_r": TARGET,
                            "hold_candles": HOLD, "costs": "Dukascopy bid/ask; 1-minute path decides stop/target order, stop first inside a minute",
                            "controls": "study control pools (random market entries, same stop-size bucket, direction, NY session, volatility, year)"},
           "criteria": [f">= {N_MIN} trades", "Benjamini-Hochberg q < 0.10 over the tests run, edge > 0",
                        "mean R > 0 with p < 0.05 at the Dukascopy spread", f"mean R > 0 at the user's ${BROKER_SPREAD:.2f} round-trip spread",
                        "edge > 0 when entered one candle later", "deflated Sharpe > 0.95 counting every trial of experiments 1-4",
                        "mean R > 0 in both halves (2003-2011, 2012-2020)"],
           "interpretation": "Training data has been examined before (experiments 1-3), so passing every criterion makes a TRAINING "
                             "CANDIDATE only. Confirmation needs unused data: the sealed final test (separate approval) or forward paper "
                             "trading. Failing means no evidence of an edge in 17 years of training data."}
    doc["sha256"] = _sha(doc)
    p.write_text(json.dumps(doc, indent=1), encoding="utf8")
    log(f"pre-registration written: {p} ({sum(t['status'] == 'run' for t in tests)} of {len(tests)} tests run)")
    return doc


def load_preregistration(symbol: str) -> dict:
    p = preregistration_path(symbol)
    if not p.exists():
        raise RuntimeError("no experiment-4 pre-registration: run the gate and commit it before any outcome is computed")
    d = json.loads(p.read_text())
    if _sha(d) != d["sha256"]:
        raise RuntimeError("experiment-4 pre-registration was edited after it was written")
    return d


# ------------------------------------------------------------------ 2. simulation (the pattern study's machinery)
def simulate_tf(symbol: str, tf: str, log=print) -> pl.DataFrame:
    load_preregistration(symbol)
    df = load_tf(symbol, tf, upto="train").sort("ts")
    S = sim.Series.from_frame(df, tf, load_m1(symbol, upto="train"))
    b = bars_from_frame(df, TF_SECONDS[tf])
    atr = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    ev = signals(df).with_columns(entry=pl.lit("market"), zone_lo=pl.lit(np.nan), zone_hi=pl.lit(np.nan))
    ev = ev.filter(pl.Series(np.isfinite(atr[ev["idx"].to_numpy()])))
    res = sim.simulate(S, study.build_orders(S, ev, atr))
    late = sim.simulate(S, study.build_orders(S, ev, atr, delay=1))
    idx = ev["idx"].to_numpy()
    fill_ts = np.where(res["fill_ts"] > 0, res["fill_ts"], S.t[idx])
    risk_atr = res["risk_px"] / atr[idx]
    vol = C.vol_bucket(atr)
    gap = study._gap_hit(study._gaps(symbol), S.t[idx], fill_ts + sim.HMAX * TF_SECONDS[tf])
    fb = np.clip(res["fill_bar"], 0, S.n - 1)
    tr = ev.select("idx", "direction").with_columns(
        signal_ts=pl.Series(S.t[idx]), entry_ts=pl.Series(fill_ts), risk_px=pl.Series(res["risk_px"]), risk_atr=pl.Series(risk_atr),
        entry=pl.lit("market"), risk_b=pl.Series(C.bucket(risk_atr, C.RISK_EDGES).astype(np.int8)), dist_b=pl.lit(-1, pl.Int8),
        width_b=pl.lit(-1, pl.Int8), session=pl.Series(C.session_ny(fill_ts)), vol=pl.Series(vol[idx]),
        period=pl.Series(C.period_key(fill_ts, "train")), segment=pl.lit("train"),
        spread_entry=pl.Series((S.ao[fb] - S.bo[fb]).astype(np.float32)), data_gap=pl.Series(gap),
        **{k: pl.Series(v) for k, v in study._compact(res).items()}, **{k: pl.Series(v) for k, v in study._compact(late, "late_").items()})
    tr = tr.with_columns(direction=pl.col("direction").cast(pl.Int8)).filter(pl.col("simulated") & ~pl.col("data_gap"))
    o = out_dir(symbol)
    o.mkdir(parents=True, exist_ok=True)
    tr.write_parquet(o / f"trades_{tf}.parquet", compression="zstd")
    log(f"{tf}: {ev.height:,} signals, {tr.height:,} trades simulated (gap-free, stop >= {sim.MIN_RISK_ATR} ATR)")
    return tr


# ------------------------------------------------------------------ 3. statistics and the pre-registered criteria
def _ctrl(tr: pl.DataFrame, pool: pl.DataFrame, k: float, h: int, prefix: str = "") -> pl.DataFrame:
    t = tr.select(*study.KEYS, "entry_ts", "risk_px", "spread_entry").with_columns(r=pl.Series(study._r(tr, k, h, prefix)))
    p = pool.select(*study.KEYS).with_columns(r=pl.Series(study._r(pool, k, h)))
    return C.expectation(t, p, "r")


def prior_trials(symbol: str) -> tuple[dict, list[float]]:
    """1/T terms of every earlier trial: experiments 1-3."""
    counts, inv = R3.prior_trials(symbol)
    p3 = R3.out_dir(symbol) / "development.json"
    if p3.exists():
        rows = [r for r in json.loads(p3.read_text())["rows"] if r.get("trades")]
        inv += [1.0 / max(r["trades"], 2) for r in rows]
        counts["experiment 3"] = len(rows)
    return counts, inv


def develop(symbol: str, log=print) -> dict:
    pre = load_preregistration(symbol)
    run_tests = [t for t in pre["tests"] if t["status"] == "run"]
    rows = []
    for t in run_tests:
        tf, d = t["tf"], (-1 if t["direction"] == "short" else 1)
        tr = pl.read_parquet(out_dir(symbol) / f"trades_{tf}.parquet").filter(pl.col("direction") == d)
        pool = pl.read_parquet(study.out_dir(symbol) / f"pool_{tf}_train.parquet")
        g = _ctrl(tr, pool, TARGET, HOLD)
        e = study._edge(g, tf, HOLD)
        gl = _ctrl(tr, pool, TARGET, HOLD, prefix="late_")
        el = study._edge(gl, tf, HOLD)
        r = g["r"].to_numpy()
        ok = np.isfinite(r)
        broker = r + (g["spread_entry"].to_numpy() - BROKER_SPREAD) / g["risk_px"].to_numpy()  # same trades, $0.30 round trip
        yr = pl.Series((g["entry_ts"].to_numpy().astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970))
        first = (yr < 2012).to_numpy()
        grid = {}
        for k in GRID_TARGETS:
            for h in GRID_HOLDS:
                gg = _ctrl(tr, pool, k, h)
                x = study._edge(gg, tf, h)
                grid[f"{k:g}R/{h}"] = {kk: x.get(kk) for kk in ("n", "mean_r", "edge", "win_rate")}
        rows.append({"tf": tf, "direction": t["direction"], "pattern": t["pattern"], "trades": int(ok.sum()), "primary": e, "late": el,
                     "broker_mean_r": float(np.nanmean(broker)), "median_risk_usd": float(np.nanmedian(g["risk_px"].to_numpy())),
                     "median_spread_r": float(np.nanmedian((g["spread_entry"] / g["risk_px"]).to_numpy())),
                     "halves": {"2003-2011": float(np.nanmean(r[first])) if first.any() else None,
                                "2012-2020": float(np.nanmean(r[~first])) if (~first).any() else None},
                     "grid": grid, "mde": Stt.mde(e.get("edge_se", float("nan")), ALPHA), "_r": r[ok]})
        log(f"{tf} {t['direction']}: {e.get('n', 0):,} trades, mean R {e.get('mean_r', float('nan')):+.3f}, edge {e.get('edge', float('nan')):+.3f}")
    counts, inv = prior_trials(symbol)
    n_trials = len(inv) + len(rows)
    null_var = float(np.mean(inv + [1.0 / max(r["trades"], 2) for r in rows]))
    ps = np.array([r["primary"].get("p_edge", 1.0) for r in rows])
    qs = Stt.bh(ps) if len(rows) else []
    cands = []
    for r, q in zip(rows, qs):
        p = r["primary"]
        r["q"] = float(q)
        r["dsr"] = R2.deflated_sharpe(r.pop("_r"), n_trials, null_var)
        hv = [v for v in r["halves"].values() if v is not None]
        r["checks"] = {"enough_trades": r["trades"] >= N_MIN, "bh_q_lt_0.10_and_edge_gt_0": r["q"] < FDR_Q and p["edge"] > 0,
                       "mean_r_gt_0_p_lt_0.05": p["mean_r"] > 0 and p["p_profit"] < ALPHA, "broker_spread_mean_r_gt_0": r["broker_mean_r"] > 0,
                       "late_entry_edge_gt_0": (r["late"].get("edge") or -1) > 0, "deflated_sharpe_gt_0.95": r["dsr"] > 0.95,
                       "positive_both_halves": len(hv) == 2 and all(v > 0 for v in hv)}
        r["status"] = "training candidate" if all(r["checks"].values()) else "no edge"
        if r["status"] == "training candidate":
            cands.append({"tf": r["tf"], "direction": r["direction"]})
    for r in rows:
        r.pop("_r", None)
    summary = {"symbol": symbol, "experiment": 4, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "preregistration_sha256": pre["sha256"], "pre_registered_tests": len(pre["tests"]), "tests_run": len(rows),
               "trials_counted_for_deflated_sharpe": n_trials, "prior_trials": counts, "candidates": cands, "rows": rows,
               "not_run": [t for t in pre["tests"] if t["status"] != "run"]}
    result_path(symbol).write_text(json.dumps(summary, indent=1, default=float), encoding="utf8")
    return summary
