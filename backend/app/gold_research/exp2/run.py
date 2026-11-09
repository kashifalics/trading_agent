"""Experiment 2 runner (docs/research/EXPERIMENT_2_PLAN.md). Analysis only; reads the TRAINING period through the sealed loader.

    python -m app.gold_research.exp2 develop     2003-2014: 36 pre-registered tests, BH, pass criteria -> frozen candidate list
    python -m app.gold_research.exp2 screen      2015-2020-02: frozen candidates only (previously examined period, NOT independent)

Every trade, strategy and control alike:
  * limit order placed at the close of the signal candle, live for WAIT candles, cancelled if a candle closes beyond the far edge;
  * CONSERVATIVE fill: the ask (longs) / bid (shorts) must trade beyond the limit by the spread at the signal candle; the fill minute
    is found on M1, adverse prices in that minute count, favourable ones do not;
  * stop = far edge + 0.1 ATR (at least 0.25 ATR from the fill); targets 1.5R / 2R (main) / 3R; time stop per timeframe;
  * exits on the bid (longs) / ask (shorts); the stop candle is replayed minute by minute; gaps through the stop lose more;
  * exit time = stop minute, the candle where the target was reached, or the time-stop candle's close; a trade is excluded only if an
    unscheduled gap (30+ minutes, not a US holiday) starts while it is open;
  * financing: nights held x the scenario's cost (fixed $0.10/oz/night is primary; none; FRED proxy when the file exists);
  * the control for a trade: random limit orders in the same period with the same direction, distance, zone width, wait, fill rule,
    holds, financing and gap rule, matched on New York session, volatility and year.
"""
import hashlib
import json
import math
from datetime import datetime, timezone

import numpy as np
import polars as pl
from scipy import stats

from app.feature_engineering.indicators import atr as atr_fn
from app.gold_research import controls as C
from app.gold_research import sim
from app.gold_research import stats as Stt
from app.gold_research.events import ATR_PERIOD, bars_from_frame, chunk_events
from app.gold_research.exp2 import data as D
from app.gold_research.exp2 import financing as F
from app.historical.config import DATA_ROOT, REPO_ROOT, TF_SECONDS
from app.historical.split import SPLIT_DIR, load_split
from app.historical.store import load_m1, load_tf
from app.historical.sync import bar_close
from app.patterns.context import compute_levels

TFS = ("H4", "H8", "D1")
HTF = {"H4": "D1", "H8": "D1", "D1": "W1"}
HOLDS = {"H4": (30, 60, 120), "H8": (15, 30, 60), "D1": (10, 20, 40)}
PRIMARY_HOLD = {"H4": 60, "H8": 30, "D1": 20}
TARGETS = (1.5, 2.0, 3.0)
PRIMARY_TARGET = 2.0
WAIT = 20
BUFFER_ATR = 0.1
MIN_TRADES = 150
FDR_Q, ALPHA = 0.10, 0.05
SETUPS = {
    "S1_trend_zone_pullback": "demand (supply) zone with the higher-timeframe structure trend in the trade's direction",
    "S2_order_block_after_bos": "order block whose impulse produced a break of structure (continuation)",
    "S3_fvg_after_displacement": "fair value gap whose middle candle is a displacement candle (range >= 2 ATR, body >= 70%)",
    "S4_broken_level_retest": "support/resistance band broken by a close >= 0.25 ATR beyond it; limit at the broken edge",
    "S5_prev_week_sweep_reclaim": "first candle of the week to trade beyond the previous week's low (high) and close back inside; limit at that level",
    "S6_range_edge_fade": "no-trend regime, close within 0.25 ATR of the previous 50-candle high (low); limit at that edge, stop 0.5 ATR beyond",
}
PRIOR_TRIALS = {"experiment 1 stage 1": 1452, "experiment 1 stage 2": 219, "experiment 1 stage 3": 260}


def out_dir(symbol: str):
    return DATA_ROOT / "research" / symbol / "exp2"


def candidates_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp2_candidates.json"


# ------------------------------------------------------------------ setups
def setup_orders(symbol: str, tf: str, df: pl.DataFrame, S: sim.Series) -> pl.DataFrame:
    """Every setup occurrence as a limit order: setup, direction, signal index, limit, far edge (cancel), stop."""
    from app.gold_research import regimes
    from app.gold_research.combos import tf_state
    b = bars_from_frame(df, TF_SECONDS[tf])
    a = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    lv = compute_levels(df["ts"], bar_close(tf, b.t), b.h, b.l)
    evs, hits, trend = chunk_events(b, a, lv)
    rows: dict[str, list] = {k: [] for k in ("setup", "direction", "idx", "limit", "far")}

    def put(setup, d, i, limit, far):
        if not (np.isfinite(limit) and np.isfinite(far)) or i + 1 >= len(b):
            return
        if (d > 0 and not (far < limit <= b.c[i])) or (d < 0 and not (far > limit >= b.c[i])):
            return  # the limit must be at or below (above) the signal close and the far edge beyond it
        rows["setup"].append(setup)
        rows["direction"].append(d)
        rows["idx"].append(i)
        rows["limit"].append(float(limit))
        rows["far"].append(float(far))

    htf = tf_state(symbol, HTF[tf], "train")
    sig_close = bar_close(tf, b.t)
    j = np.searchsorted(htf["close"], sig_close, side="right") - 1
    htf_trend = np.where(j >= 0, htf["trend"][np.maximum(j, 0)], 0)
    for e in evs:
        if e.kind in ("demand_zone", "supply_zone"):
            d = 1 if e.kind == "demand_zone" else -1
            if htf_trend[e.idx] == d:
                put("S1_trend_zone_pullback", d, e.idx, e.high if d > 0 else e.low, e.low if d > 0 else e.high)
        elif e.kind == "breakout":
            d = 1 if e.direction == "bullish" else -1
            put("S4_broken_level_retest", d, e.idx, e.high if d > 0 else e.low, e.low if d > 0 else e.high)
    pats, hidx, hdir, hstop, hlo, hhi = hits.rows()
    for k, pid in enumerate(pats):
        i, d = int(hidx[k]), int(hdir[k])
        if pid == "order_block_bos":
            put("S2_order_block_after_bos", d, i, hhi[k] if d > 0 else hlo[k], hlo[k] if d > 0 else hhi[k])
        elif pid == "displacement_imbalance":
            put("S3_fvg_after_displacement", d, i, hhi[k] if d > 0 else hlo[k], hlo[k] if d > 0 else hhi[k])
        elif pid == "pw_low_sweep":
            put("S5_prev_week_sweep_reclaim", 1, i, lv.pwl[i], b.l[i])
        elif pid == "pw_high_sweep":
            put("S5_prev_week_sweep_reclaim", -1, i, lv.pwh[i], b.h[i])
    reg = regimes.compute(b.t, b.o, b.h, b.l, b.c, a, trend)
    from app.patterns.candles import _roll_max, _roll_min, _sh
    hi50, lo50 = _sh(_roll_max(b.h, 50), 1), _sh(_roll_min(b.l, 50), 1)
    none = np.asarray(reg["trend_regime"]) == "none"
    with np.errstate(invalid="ignore"):
        near_hi = none & (b.c <= hi50) & (b.c >= hi50 - 0.25 * a)
        near_lo = none & (b.c >= lo50) & (b.c <= lo50 + 0.25 * a)
    for i in np.flatnonzero(near_hi & ~np.r_[False, near_hi[:-1]]):
        put("S6_range_edge_fade", -1, int(i), hi50[i], hi50[i] + 0.4 * a[i])
    for i in np.flatnonzero(near_lo & ~np.r_[False, near_lo[:-1]]):
        put("S6_range_edge_fade", 1, int(i), lo50[i], lo50[i] - 0.4 * a[i])
    out = pl.DataFrame(rows, schema={"setup": pl.Utf8, "direction": pl.Int8, "idx": pl.Int64, "limit": pl.Float64, "far": pl.Float64})
    return out.unique(subset=["setup", "direction", "idx"], keep="first", maintain_order=True).sort("idx")


# ------------------------------------------------------------------ simulation with costs and exit times
def simulate_orders(S: sim.Series, a: np.ndarray, d: np.ndarray, idx: np.ndarray, limit: np.ndarray, far: np.ndarray, tf: str,
                    gs: np.ndarray, roll, fred) -> dict:
    through = (S.ao - S.bo)[idx]  # conservative fill: trade beyond the limit by the spread at the signal candle
    o = sim.Orders(d=d.astype(np.int64), entry_bar=idx + 1, stop=far - d * BUFFER_ATR * a[idx], atr=a[idx], limit=limit, cancel=far,
                   wait=WAIT, through=through)
    res = sim.simulate(S, o, holds=HOLDS[tf], hit_targets=TARGETS)
    out = {"simulated": res["simulated"], "fill_ts": res["fill_ts"], "fill_bar": res["fill_bar"], "risk_px": res["risk_px"],
           "entry_px": res["entry_px"], "spread_signal": through}
    step = TF_SECONDS[tf]
    for k in TARGETS:
        for h in HOLDS[tf]:
            r = sim.r_multiple(res, k, h)
            hit = res[f"hit_{k:g}"]
            reached = res[f"mfe_{h}"] >= k
            stopped = res[f"stopped_{h}"]
            end_bar = res["fill_bar"] + h - 1
            exit_ts = np.where(reached, S.t[np.clip(hit, 0, S.n - 1)] + step,
                               np.where(stopped, res["stop_ts"], S.t[np.clip(end_bar, 0, S.n - 1)] + step))
            key = f"{k:g}R_{h}"
            ok = res["simulated"]
            out[f"r_{key}"] = np.where(ok, r, np.nan)
            out[f"exit_{key}"] = np.where(ok, exit_ts, -1)
            out[f"gap_{key}"] = ok & D.gap_between(gs, res["fill_ts"], exit_ts)
            for sc in F.SCENARIOS:
                c = F.cost_usd_per_oz(sc, d, res["fill_ts"], exit_ts, res["entry_px"], roll, fred)
                out[f"fin_{sc}_{key}"] = None if c is None else c / res["risk_px"]
    return out


def _frame(sim_out: dict, extra: dict) -> pl.DataFrame:
    cols = {k: v for k, v in sim_out.items() if v is not None}
    return pl.DataFrame({**extra, **{k: pl.Series(k, v) for k, v in cols.items()}})


def run_tf(symbol: str, tf: str, log=print) -> None:
    """Simulate every setup order and the control pool on the training period (development and screening are separated later
    by entry and exit time)."""
    df = load_tf(symbol, tf, upto="train").sort("ts")
    S = sim.Series.from_frame(df, tf, load_m1(symbol, upto="train"))
    b = bars_from_frame(df, TF_SECONDS[tf])
    a = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    gs = D.unscheduled_starts(symbol)
    years = df["ts"].dt.year()
    roll = F.rollovers(int(years.min()), int(years.max()) + 1)
    fred = F.load_fred()
    orders = setup_orders(symbol, tf, df, S)
    log(f"{tf}: {orders.height:,} setup orders")
    idx = orders["idx"].to_numpy()
    d = orders["direction"].to_numpy().astype(np.int64)
    so = simulate_orders(S, a, d, idx, orders["limit"].to_numpy(), orders["far"].to_numpy(), tf, gs, roll, fred)
    vol = C.vol_bucket(a)
    dist = d * (S.bc[idx] - orders["limit"].to_numpy()) / a[idx]
    width = np.abs(orders["limit"].to_numpy() - orders["far"].to_numpy()) / a[idx]
    trades = _frame(so, {"setup": orders["setup"], "direction": orders["direction"], "idx": orders["idx"],
                         "signal_ts": pl.Series(S.t[idx]), "dist_b": pl.Series(C.bucket(dist, C.DIST_EDGES).astype(np.int8)),
                         "width_b": pl.Series(C.bucket(width, C.WIDTH_EDGES).astype(np.int8)), "vol": pl.Series(vol[idx])})
    trades = trades.filter(pl.col("simulated"))
    trades = trades.with_columns(session=pl.Series(C.session_ny(trades["fill_ts"].to_numpy())))
    # controls: random signal candles, both directions, the limit-geometry grid of experiment 1 (same buckets)
    rng = np.random.default_rng(sum(map(ord, f"exp2{symbol}{tf}")))
    elig = np.flatnonzero(np.isfinite(a) & (np.arange(S.n) + max(HOLDS[tf]) + WAIT + 2 < S.n))
    bars = np.sort(rng.choice(elig, min(len(elig), 20_000), replace=False))
    frames = []
    for dd in (1, -1):
        for i_, dc in enumerate(C.DIST_CENTRES):
            for j_, wc in enumerate(C.WIDTH_CENTRES):
                lim = S.bc[bars] - dd * dc * a[bars]
                far = lim - dd * wc * a[bars]
                co = simulate_orders(S, a, np.full(len(bars), dd), bars, lim, far, tf, gs, roll, fred)
                frames.append(_frame(co, {"direction": pl.Series(np.full(len(bars), dd, np.int8)), "signal_ts": pl.Series(S.t[bars]),
                                          "dist_b": pl.Series(np.full(len(bars), i_, np.int8)), "width_b": pl.Series(np.full(len(bars), j_, np.int8)),
                                          "vol": pl.Series(vol[bars])}).filter(pl.col("simulated")))
    pool = pl.concat(frames)
    pool = pool.with_columns(session=pl.Series(C.session_ny(pool["fill_ts"].to_numpy())))
    o = out_dir(symbol)
    o.mkdir(parents=True, exist_ok=True)
    trades.write_parquet(o / f"trades_{tf}.parquet", compression="zstd")
    pool.write_parquet(o / f"pool_{tf}.parquet", compression="zstd")
    log(f"{tf}: {trades.height:,} filled setup trades, {pool.height:,} filled control trades")


# ------------------------------------------------------------------ statistics
def segment_frame(df: pl.DataFrame, seg: str, key: str, symbol: str) -> pl.DataFrame:
    s = D.load(symbol)
    a = int(datetime.fromisoformat(s["development"]["start"]).timestamp())
    dev_end = int(datetime.fromisoformat(s["development"]["end_exclusive"]).timestamp())
    end = int(datetime.fromisoformat(s["screening"]["end_exclusive"]).timestamp())
    lo, hi = (a, dev_end) if seg == "development" else (dev_end, end)
    ok = (pl.col("fill_ts") >= lo) & (pl.col(f"exit_{key}") < hi) & ~pl.col(f"gap_{key}") & pl.col(f"r_{key}").is_not_nan()
    year = (pl.col("fill_ts") * 1_000_000).cast(pl.Datetime("us")).dt.year()
    return df.filter(ok).with_columns(period=pl.concat_str([year.cast(pl.Utf8), pl.lit(":" + seg)]), year=year, segment=pl.lit(seg),
                                      entry=pl.lit("limit"), risk_b=pl.lit(-1, pl.Int8), entry_ts=pl.col("fill_ts"))


def net_r(df: pl.DataFrame, key: str, scenario: str = "fixed_0.10", spread_x: float = 1.0, slip: float = 0.0) -> np.ndarray | None:
    col = f"fin_{scenario}_{key}"
    if col not in df.columns:
        return None
    r = df[f"r_{key}"].to_numpy() - df[col].to_numpy()
    if spread_x != 1.0:
        r = r - (spread_x - 1.0) * df["spread_signal"].to_numpy() / df["risk_px"].to_numpy()
    if slip:
        r = r - 2 * slip / df["risk_px"].to_numpy()
    return r


def evaluate(tr: pl.DataFrame, pool: pl.DataFrame, key: str, tf: str, hold: int, scenario: str = "fixed_0.10") -> dict:
    t = tr.with_columns(r=pl.Series(net_r(tr, key, scenario)))
    p = pool.with_columns(r=pl.Series(net_r(pool, key, scenario)))
    ex = C.expectation(t.select("entry", "direction", "risk_b", "dist_b", "width_b", "session", "vol", "period", "segment", "entry_ts",
                                "year", "r", "risk_px", "spread_signal", f"fin_{scenario}_{key}", f"r_{key}"),
                       p.select("entry", "direction", "risk_b", "dist_b", "width_b", "session", "vol", "period", "segment", "r"), "r")
    e = Stt.edge_stats(ex["r"].to_numpy(), ex["ctrl_mean"].to_numpy(), ex["ctrl_var"].to_numpy(), ex["ctrl_n"].to_numpy().astype(float),
                       ex["ctrl_cell"].to_numpy(), ex["entry_ts"].to_numpy(), hold * TF_SECONDS[tf])
    return {**e, "_frame": ex}


def deflated_sharpe(r: np.ndarray, n_trials: int, null_var: float) -> float:
    r = r[np.isfinite(r)]
    if len(r) < 3 or r.std() == 0:
        return float("nan")
    sr = r.mean() / r.std(ddof=1)
    g = 0.5772156649
    sr0 = math.sqrt(null_var) * ((1 - g) * stats.norm.ppf(1 - 1 / n_trials) + g * stats.norm.ppf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(max(1e-12, 1 - stats.skew(r) * sr + (stats.kurtosis(r, fisher=False) - 1) / 4 * sr ** 2))
    return float(stats.norm.cdf((sr - sr0) * math.sqrt(len(r) - 1) / den))


def _prior_null_var(symbol: str) -> tuple[int, float]:
    """All earlier trials' sample sizes (experiment 1, stages 1-3) for the cumulative deflated Sharpe benchmark."""
    from app.gold_research import study
    ns = []
    for stage in (1, 2, 3):
        p = study.out_dir(symbol) / f"discovery_stage{stage}.json"
        if p.exists():
            ns += [r["primary"]["n"] for r in json.loads(p.read_text())["rows"] if "q" in r and not r.get("earlier_stage")]
    return len(ns), float(np.mean(1.0 / np.maximum(np.array(ns, float), 2))) if ns else 0.0


def develop(symbol: str, log=print) -> dict:
    D.freeze_split(symbol)
    rows = []
    for tf in TFS:
        o = out_dir(symbol)
        tr, pool = pl.read_parquet(o / f"trades_{tf}.parquet"), pl.read_parquet(o / f"pool_{tf}.parquet")
        h = PRIMARY_HOLD[tf]
        key = f"{PRIMARY_TARGET:g}R_{h}"
        dev_t, dev_p = segment_frame(tr, "development", key, symbol), segment_frame(pool, "development", key, symbol)
        for setup in SETUPS:
            for d in (1, -1):
                g = dev_t.filter((pl.col("setup") == setup) & (pl.col("direction") == d))
                row = {"tf": tf, "setup": setup, "direction": "long" if d > 0 else "short", "trades": g.height}
                if g.height:
                    e = evaluate(g, dev_p, key, tf, h)
                    fr = e.pop("_frame")
                    row["main"] = e
                    cl = Stt.cluster_ids(fr["entry_ts"].to_numpy(), h * TF_SECONDS[tf])
                    row["stress"] = {}
                    for name, kw in (("slippage_0.10", {"slip": 0.10}), ("spread_x1.5", {"spread_x": 1.5}), ("no_financing", {"scenario": "none"}),
                                     ("fred_proxy", {"scenario": "fred_proxy"})):
                        v = net_r(g, key, **kw)
                        row["stress"][name] = None if v is None else Stt.clustered_mean(v[np.isfinite(v)], cl[np.isfinite(v)])
                    yr = fr.group_by("year").agg(pl.col("r").mean().alias("m"), pl.len().alias("n")).sort("year")
                    row["years"] = yr.rows()
                    row["share_positive_years"] = float((yr["m"] > 0).mean()) if yr.height else 0.0
                    row["_r"] = fr["r"].to_numpy().tolist()
                    row["grid"] = {f"{k:g}R_{hh}": {"mean_r": float(np.nanmean(net_r(g, f'{k:g}R_{hh}'))), "n": int(g.height)}
                                   for k in TARGETS for hh in HOLDS[tf]}
                rows.append(row)
        log(f"{tf}: development statistics done")
    tested = [r for r in rows if r.get("main") and r["trades"] >= MIN_TRADES and np.isfinite(r["main"].get("edge_se", np.nan))]
    for r, q in zip(tested, Stt.bh(np.array([r["main"]["p_edge"] for r in tested]))):
        r["q"] = float(q)
    n_prior, v_prior = _prior_null_var(symbol)
    n_trials = n_prior + len(rows)
    null_var = float(np.mean([v_prior] * n_prior + [1.0 / max(r["trades"], 2) for r in rows])) if rows else 1.0
    for r in rows:
        r["dsr"] = deflated_sharpe(np.array(r.pop("_r", [])), n_trials, null_var) if r.get("main") else float("nan")
        crit = {}
        if "q" in r:
            m, st = r["main"], r["stress"]
            crit = {"bh_q_lt_0.10_and_edge_positive": r["q"] < FDR_Q and m["edge"] > 0,
                    "profitable_main": m["mean_r"] > 0 and m["p_profit"] < ALPHA,
                    "profitable_slippage_0.10": st["slippage_0.10"]["mean"] > 0, "profitable_spread_x1.5": st["spread_x1.5"]["mean"] > 0,
                    "deflated_sharpe_gt_0.95": r["dsr"] > 0.95, "positive_years_ge_60pct": r["share_positive_years"] >= 0.60}
        r["criteria"] = crit
        r["status"] = ("too few trades" if "q" not in r else "CANDIDATE" if all(crit.values()) else
                       "no: " + ", ".join(k for k, v in crit.items() if not v))
    cands = [{"tf": r["tf"], "setup": r["setup"], "direction": r["direction"]} for r in rows if r["status"] == "CANDIDATE"]
    summary = {"symbol": symbol, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "segment": "development 2003-2014",
               "tests": len(tested), "pre_registered_tests": len(rows), "trials_counted_for_deflated_sharpe": n_trials,
               "prior_trials": PRIOR_TRIALS, "fred": F.fred_status(), "candidates": cands, "rows": rows}
    o = out_dir(symbol)
    (o / "development.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf8")
    p = candidates_path(symbol)
    if not p.exists():
        doc = {"symbol": symbol, "created": summary["generated"], "candidates": cands, "tests": len(tested),
               "main_setting": {"target_r": PRIMARY_TARGET, "holds": PRIMARY_HOLD, "fill": "conservative (trade through by the spread)",
                                "financing": "fixed $0.10/oz/night", "wait": WAIT}, "exp2_split_sha256": D.load(symbol)["sha256"]}
        doc["sha256"] = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
        p.write_text(json.dumps(doc, indent=1), encoding="utf8")
    else:
        log(f"{p.name} already frozen: not overwritten")
    return summary


def screen(symbol: str, log=print) -> dict:
    f = json.loads(candidates_path(symbol).read_text())
    body = {k: v for k, v in f.items() if k != "sha256"}
    if hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != f["sha256"]:
        raise RuntimeError("experiment-2 candidate list was edited after it was frozen")
    rows = []
    for c in f["candidates"]:
        tf, h = c["tf"], PRIMARY_HOLD[c["tf"]]
        key = f"{PRIMARY_TARGET:g}R_{h}"
        o = out_dir(symbol)
        tr, pool = pl.read_parquet(o / f"trades_{tf}.parquet"), pl.read_parquet(o / f"pool_{tf}.parquet")
        d = 1 if c["direction"] == "long" else -1
        g = segment_frame(tr, "screening", key, symbol).filter((pl.col("setup") == c["setup"]) & (pl.col("direction") == d))
        e = evaluate(g, segment_frame(pool, "screening", key, symbol), key, tf, h) if g.height else {"n": 0}
        e.pop("_frame", None)
        rows.append({**c, "screen": e})
    ok = [r for r in rows if r["screen"].get("n", 0) >= 30]
    for r, hp in zip(ok, Stt.holm(np.array([r["screen"]["p_edge"] for r in ok]))):
        r["holm_p"] = float(hp)
    for r in rows:
        s = r["screen"]
        r["verdict"] = ("too few screening trades" if "holm_p" not in r else
                        "passes screen" if r["holm_p"] < ALPHA and s["edge"] > 0 and s["mean_r"] > 0 and s["p_profit"] < ALPHA else "fails screen")
    out = {"symbol": symbol, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "segment": "screening 2015-2020-02 (previously examined; NOT independent validation)", "candidates_sha256": f["sha256"], "rows": rows}
    (out_dir(symbol) / "screening.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf8")
    return out


def report_path(symbol: str):
    return REPO_ROOT / "docs" / "reports" / f"{symbol}_EXPERIMENT2.md"


def verify_scope(symbol: str) -> dict:
    """Evidence that nothing outside the training period was read."""
    s = load_split(symbol)
    t_end = int(datetime.fromisoformat(s["train"]["end_exclusive"]).timestamp())
    out = {}
    for p in sorted(out_dir(symbol).glob("*.parquet")):
        df = pl.read_parquet(p)
        ex = [c for c in df.columns if c.startswith("exit_")]
        out[p.stem] = {"rows": df.height, "last_fill": int(df["fill_ts"].max()) if df.height else None,
                       "all_exits_before_training_end": bool(all((df[c].max() or 0) < t_end for c in ex)) if df.height else True}
    out["seal_log_exists"] = (SPLIT_DIR / f"{symbol}_seal_log.md").exists()
    return out
