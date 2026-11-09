"""Pattern study on the sealed gold history (docs/PATTERN_STUDY.md). Analysis only: nothing here places orders.

    python -m app.gold_research discover --tfs M5,M15,M30,H1,H4,D1     training segment only -> candidates (frozen list)
    python -m app.gold_research validate                              validation segment, ONLY the frozen candidates

Pre-registered main test per pattern (decided before any result was seen): the pattern's natural entry (next open; zones: limit at
the near edge), its structural stop plus STOP_BUFFER_ATR, a 2R target and a 48-candle hold, costs = the real Dukascopy spread.
Edge = R minus the matched control mean (controls.py). Discovery: Benjamini-Hochberg over every test with at least MIN_N trades.
Validation: Holm over the frozen candidates, plus a one-candle-later entry check for market entries. Every other target / holding
period is computed for description only and never used to pick anything.
"""
import hashlib
import json
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.feature_engineering.indicators import atr as atr_fn
from app.gold_research import controls as C
from app.gold_research import sim
from app.gold_research import stats as Stt
from app.gold_research.events import ATR_PERIOD, bars_from_frame, find_events
from app.historical.config import CLEAN, DATA_ROOT, REPO_ROOT, TF_SECONDS
from app.historical.split import SPLIT_DIR, load_split
from app.historical.store import load_m1, load_tf
from app.historical.sync import bar_close
from app.patterns.context import compute_levels

STUDY_TFS = ("M5", "M15", "M30", "H1", "H4", "D1")
PRIMARY_TARGET, PRIMARY_HOLD = 2.0, 48
TARGETS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
STOP_BUFFER_ATR = C.STOP_BUFFER_ATR
ZONE_WAIT = C.ZONE_WAIT
MIN_N = 100
FDR_Q, ALPHA = 0.10, 0.05
POOL_BARS = 40_000
BROKER_SPREAD = 0.30


def out_dir(symbol: str):
    return DATA_ROOT / "research" / symbol


def candidates_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_candidates.json"


def _ts(x: np.ndarray) -> np.ndarray:
    return x.astype(np.int64)


def build_orders(S: sim.Series, ev: pl.DataFrame, atr: np.ndarray, delay: int = 0) -> sim.Orders:
    idx = ev["idx"].to_numpy()
    d = ev["direction"].to_numpy().astype(np.int64)
    a = atr[idx]
    zone = (ev["entry"] == "zone_retest").to_numpy()
    lvl = ev["stop_level"].to_numpy()
    lo, hi = ev["zone_lo"].to_numpy(), ev["zone_hi"].to_numpy()
    eb = idx + 1 + (0 if delay == 0 else delay)
    ebc = np.clip(eb, 0, S.n - 1)
    px = np.where(d > 0, S.ao[ebc], S.bo[ebc])
    stop = np.where(np.isfinite(lvl), lvl - d * STOP_BUFFER_ATR * a, px - d * 1.0 * a)
    limit = np.where(zone, np.where(d > 0, hi, lo), np.nan)
    cancel = np.where(zone, np.where(d > 0, lo, hi), np.nan)
    if delay:
        eb = np.where(zone, -1, eb)  # the delay check is for market entries; a limit order has no first-print fill to exploit
    return sim.Orders(d=d, entry_bar=np.where(eb < S.n, eb, -1), stop=stop, atr=a, limit=limit, cancel=cancel, wait=ZONE_WAIT)


def _gaps(symbol: str) -> np.ndarray:
    p = CLEAN / symbol / "gaps.parquet"
    if not p.exists():
        return np.array([], dtype=np.int64)
    g = pl.read_parquet(p)
    return np.sort(g.filter(pl.col("material"))["start"].dt.epoch("s").to_numpy()) if g.height else np.array([], dtype=np.int64)


def _gap_hit(gs: np.ndarray, start: np.ndarray, end: np.ndarray) -> np.ndarray:
    if len(gs) == 0:
        return np.zeros(len(start), dtype=bool)
    return np.searchsorted(gs, end, side="right") > np.searchsorted(gs, start, side="left")


def _compact(res: dict, prefix: str = "") -> dict:
    out = {f"{prefix}stop_r": res["stop_r"].astype(np.float32), f"{prefix}simulated": res["simulated"]}
    for h in sim.HOLDS:
        for c in (f"mfe_{h}", f"mfe_opt_{h}", f"stopped_{h}", f"end_r_{h}"):
            out[f"{prefix}{c}"] = res[c]
    return out


def run_timeframe(symbol: str, tf: str, segment: str, log_file: str | None = None) -> str:
    """Simulate every directional pattern event and the control pool of one timeframe inside one segment."""
    def log(m: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {symbol} {tf} {segment}: {m}"
        print(line, flush=True)
        if log_file:
            with open(log_file, "a", encoding="utf8") as f:
                f.write(line + "\n")

    split = load_split(symbol)
    seg_start = 0 if segment == "train" else int(datetime.fromisoformat(split["train"]["end_exclusive"]).timestamp())
    df = load_tf(symbol, tf, upto=segment)
    m1 = load_m1(symbol, upto=segment)
    S = sim.Series.from_frame(df, tf, m1)
    b = bars_from_frame(df.sort("ts"), TF_SECONDS[tf])
    atr = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    log(f"{S.n:,} candles to {df['ts'].max():%Y-%m-%d}; finding patterns")
    levels = compute_levels(df.sort("ts")["ts"], bar_close(tf, b.t), b.h, b.l)
    ev, trend = find_events(b, atr, log=log, label=tf, cache_dir=out_dir(symbol) / "event_chunks" / tf, levels=levels)
    ev = ev.filter(pl.col("direction") != 0)
    log(f"{ev.height:,} directional events; simulating")
    res = sim.simulate(S, build_orders(S, ev, atr))
    late = sim.simulate(S, build_orders(S, ev, atr, delay=1))
    vol = C.vol_bucket(atr)
    idx = ev["idx"].to_numpy()
    fill_ts = np.where(res["fill_ts"] > 0, res["fill_ts"], S.t[idx])
    a = atr[idx]
    risk_atr = res["risk_px"] / a
    zone = (ev["entry"] == "zone_retest").to_numpy()
    d = ev["direction"].to_numpy()
    near = np.where(d > 0, ev["zone_hi"].to_numpy(), ev["zone_lo"].to_numpy())
    dist = d * (S.bc[idx] - near) / a
    width = (ev["zone_hi"].to_numpy() - ev["zone_lo"].to_numpy()) / a
    gs = _gaps(symbol)
    gap = _gap_hit(gs, S.t[idx], fill_ts + sim.HMAX * TF_SECONDS[tf])
    fb = np.clip(res["fill_bar"], 0, S.n - 1)
    trades = ev.with_columns(
        signal_ts=pl.Series(S.t[idx]), entry_ts=pl.Series(fill_ts), risk_px=pl.Series(res["risk_px"]), risk_atr=pl.Series(risk_atr),
        risk_b=pl.Series(np.where(zone, -1, C.bucket(risk_atr, C.RISK_EDGES)).astype(np.int8)),
        dist_b=pl.Series(np.where(zone, C.bucket(dist, C.DIST_EDGES), -1).astype(np.int8)),
        width_b=pl.Series(np.where(zone, C.bucket(width, C.WIDTH_EDGES), -1).astype(np.int8)),
        entry_kind=pl.Series(np.where(zone, "limit", "market")), session=pl.Series(C.session_ny(fill_ts)), vol=pl.Series(vol[idx]),
        structure=pl.Series(np.select([trend[idx] * d > 0, trend[idx] * d < 0], ["with", "against"], "none")),
        spread_entry=pl.Series((S.ao[fb] - S.bo[fb]).astype(np.float32)), data_gap=pl.Series(gap),
        **{k: pl.Series(v) for k, v in _compact(res).items()}, **{k: pl.Series(v) for k, v in _compact(late, "late_").items()},
    ).rename({"entry": "entry_rule"}).rename({"entry_kind": "entry"})
    trades = trades.with_columns(period=pl.Series(C.period_key(fill_ts, segment)), segment=pl.lit(segment))
    trades = trades.filter(pl.col("simulated") & ~pl.col("data_gap") & (pl.col("entry_ts") >= seg_start))
    # control pool: random candles of this segment only
    rng = np.random.default_rng(sum(map(ord, f"{symbol}{tf}{segment}")))
    eligible = np.flatnonzero((S.t >= seg_start) & np.isfinite(atr) & (np.arange(S.n) + sim.HMAX + 2 < S.n))
    bars = np.sort(rng.choice(eligible, min(POOL_BARS, len(eligible)), replace=False))
    log(f"{trades.height:,} trades kept; simulating {len(bars):,} control candles")
    pool = C.pool(S, atr, vol, bars, segment)
    out = out_dir(symbol)
    out.mkdir(parents=True, exist_ok=True)
    trades.write_parquet(out / f"trades_{tf}_{segment}.parquet", compression="zstd")
    pool.write_parquet(out / f"pool_{tf}_{segment}.parquet", compression="zstd")
    log(f"saved trades_{tf}_{segment}.parquet and pool_{tf}_{segment}.parquet")
    return tf


def run(symbol: str, tfs: list[str], segment: str, workers: int = 3, log: Callable[[str], None] = print,
        log_file: str | None = None) -> None:
    import os
    os.environ.setdefault("POLARS_MAX_THREADS", "1")
    with ProcessPoolExecutor(max_workers=max(1, min(workers, len(tfs)))) as ex:
        for tf in ex.map(run_timeframe, [symbol] * len(tfs), tfs, [segment] * len(tfs), [log_file] * len(tfs)):
            log(f"{symbol} {tf} {segment}: done")


# ------------------------------------------------------------------ evaluation
def _r(df: pl.DataFrame, k: float, h: int, prefix: str = "", optimistic: bool = False) -> np.ndarray:
    o = {"simulated": df[f"{prefix}simulated"].to_numpy() if f"{prefix}simulated" in df.columns else np.ones(df.height, bool),
         "stop_r": df[f"{prefix}stop_r"].to_numpy(), f"mfe_{h}": df[f"{prefix}mfe_{h}"].to_numpy(),
         f"mfe_opt_{h}": df[f"{prefix}mfe_opt_{h}"].to_numpy(), f"stopped_{h}": df[f"{prefix}stopped_{h}"].to_numpy(),
         f"end_r_{h}": df[f"{prefix}end_r_{h}"].to_numpy()}
    return sim.r_multiple(o, k, h, optimistic)


KEYS = ["entry", "direction", "risk_b", "dist_b", "width_b", "session", "vol", "period", "segment"]
KEEP = ["pattern", "family", "entry_ts", "risk_px", "spread_entry", "structure"]


def _with_ctrl(trades: pl.DataFrame, pool: pl.DataFrame, k: float, h: int, prefix: str = "") -> pl.DataFrame:
    """Trades (only the columns statistics need) with R for target k / hold h and their matched control expectation."""
    t = trades.select(*KEYS, *KEEP).with_columns(r=pl.Series(_r(trades, k, h, prefix)))
    p = pool.select(*KEYS).with_columns(r=pl.Series(_r(pool, k, h)))
    return C.expectation(t, p, "r")


def _edge(df: pl.DataFrame, tf: str, h: int, r_override: np.ndarray | None = None) -> dict:
    r = df["r"].to_numpy() if r_override is None else r_override
    return Stt.edge_stats(r, df["ctrl_mean"].to_numpy(), df["ctrl_var"].to_numpy(), df["ctrl_n"].to_numpy().astype(float),
                          df["ctrl_cell"].to_numpy(), df["entry_ts"].to_numpy(), h * TF_SECONDS[tf])


def load_frames(symbol: str, tfs, segment: str) -> dict[str, tuple[pl.DataFrame, pl.DataFrame]]:
    o = out_dir(symbol)
    return {tf: (pl.read_parquet(o / f"trades_{tf}_{segment}.parquet"), pl.read_parquet(o / f"pool_{tf}_{segment}.parquet"))
            for tf in tfs if (o / f"trades_{tf}_{segment}.parquet").exists()}


def _opt_share(tr: pl.DataFrame, pat: str, d: int) -> float:
    """Share of trades whose main-test result would change if the stop minute's favourable extreme came first."""
    g = tr.filter((pl.col("pattern") == pat) & (pl.col("direction") == d))
    a, b = _r(g, PRIMARY_TARGET, PRIMARY_HOLD), _r(g, PRIMARY_TARGET, PRIMARY_HOLD, optimistic=True)
    ok = np.isfinite(a)
    return float(np.mean(a[ok] != b[ok])) if ok.any() else 0.0


def discover(symbol: str, tfs, log: Callable[[str], None] = print) -> dict:
    """Training segment only. Primary test per (timeframe, pattern, direction); BH; freeze the candidate list."""
    frames = load_frames(symbol, tfs, "train")
    rows = []
    for tf, (tr, pool) in frames.items():
        prim = _with_ctrl(tr, pool, PRIMARY_TARGET, PRIMARY_HOLD)
        late = _with_ctrl(tr, pool, PRIMARY_TARGET, PRIMARY_HOLD, prefix="late_")
        grid: dict[tuple, dict] = {}
        for k in TARGETS:  # descriptive grid, one target/hold at a time (memory)
            for h in sim.HOLDS:
                full = _with_ctrl(tr, pool, k, h)
                for (pat, d), gg in full.group_by(["pattern", "direction"], maintain_order=True):
                    e = _edge(gg, tf, h)
                    grid.setdefault((pat, d), {})[f"{k:g}R/{h}"] = {kk: e.get(kk) for kk in ("n", "mean_r", "edge", "edge_se", "win_rate")}
                del full
        for (pat, d), g in prim.group_by(["pattern", "direction"], maintain_order=True):
            e = _edge(g, tf, PRIMARY_HOLD)
            gl = late.filter((pl.col("pattern") == pat) & (pl.col("direction") == d))
            row = {"tf": tf, "pattern": pat, "direction": "long" if d > 0 else "short", "family": g["family"][0], "entry": g["entry"][0],
                   "primary": e, "late": _edge(gl, tf, PRIMARY_HOLD) if gl.height else {"n": 0},
                   "optimistic_share_changed": _opt_share(tr, pat, d),
                   "ctrl_levels": g["ctrl_level"].value_counts().sort("ctrl_level").rows(),
                   "by_session": {k: _edge(x, tf, PRIMARY_HOLD).get("mean_r") for (k,), x in g.group_by(["session"])},
                   "by_structure": {k: _edge(x, tf, PRIMARY_HOLD).get("mean_r") for (k,), x in g.group_by(["structure"])},
                   "grid": grid.get((pat, d), {})}
            row["mde"] = Stt.mde(e.get("edge_se", float("nan")), ALPHA)
            rows.append(row)
        log(f"{symbol} {tf}: {len([r for r in rows if r['tf'] == tf])} pattern/direction tests evaluated")
    tested = [r for r in rows if r["primary"].get("n", 0) >= MIN_N and np.isfinite(r["primary"].get("edge_se", np.nan))]
    if tested:
        for r, q in zip(tested, Stt.bh(np.array([r["primary"]["p_edge"] for r in tested]))):
            r["q"] = float(q)
    for r in rows:
        r["status"] = ("not enough trades" if "q" not in r else
                       "candidate" if r["q"] < FDR_Q and r["primary"]["edge"] > 0 else "no edge in training")
    cands = [{"tf": r["tf"], "pattern": r["pattern"], "direction": r["direction"]} for r in rows if r["status"] == "candidate"]
    summary = {"symbol": symbol, "segment": "train", "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "primary": {"target_r": PRIMARY_TARGET, "hold_candles": PRIMARY_HOLD, "costs": "Dukascopy bid/ask"},
               "tests": len(tested), "candidates": cands, "rows": rows, "split_sha256": load_split(symbol)["sha256"]}
    out_dir(symbol).mkdir(parents=True, exist_ok=True)
    (out_dir(symbol) / "discovery.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf8")
    freeze = {"symbol": symbol, "created": summary["generated"], "primary": summary["primary"], "fdr_q": FDR_Q, "min_n": MIN_N,
              "tests": len(tested), "candidates": cands, "split_sha256": summary["split_sha256"]}
    freeze["sha256"] = hashlib.sha256(json.dumps(freeze, sort_keys=True).encode()).hexdigest()
    p = candidates_path(symbol)
    if p.exists():
        log(f"{p.name} exists: not overwritten (candidates are frozen once). Delete it only if discovery itself was wrong, and say so.")
    else:
        p.write_text(json.dumps(freeze, indent=1), encoding="utf8")
    return summary


def validate(symbol: str, log: Callable[[str], None] = print) -> dict:
    """Validation segment, frozen candidates only: Holm, one-candle-later entry, profitability under each cost scenario."""
    frozen = json.loads(candidates_path(symbol).read_text())
    body = {k: v for k, v in frozen.items() if k != "sha256"}
    if hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != frozen["sha256"]:
        raise RuntimeError("candidate list was edited after it was frozen")
    tfs = sorted({c["tf"] for c in frozen["candidates"]})
    frames = load_frames(symbol, tfs, "validation")
    rows = []
    for c in frozen["candidates"]:
        tr, pool = frames[c["tf"]]
        d = 1 if c["direction"] == "long" else -1
        g = tr.filter((pl.col("pattern") == c["pattern"]) & (pl.col("direction") == d))
        prim = _with_ctrl(g, pool, PRIMARY_TARGET, PRIMARY_HOLD)
        late = _with_ctrl(g, pool, PRIMARY_TARGET, PRIMARY_HOLD, prefix="late_")
        e = _edge(prim, c["tf"], PRIMARY_HOLD)
        r = prim["r"].to_numpy()
        risk = prim["risk_px"].to_numpy()
        spread = prim["spread_entry"].to_numpy()
        costs = {"broker_0.30": r + (spread - BROKER_SPREAD) / risk, "slippage_0.10_per_side": r - 0.20 / risk}
        scen = {k: Stt.clustered_mean(v[np.isfinite(v)], Stt.cluster_ids(prim["entry_ts"].to_numpy()[np.isfinite(v)],
                                                                            PRIMARY_HOLD * TF_SECONDS[c["tf"]])) for k, v in costs.items()}
        rows.append({**c, "entry": g["entry"][0] if g.height else "market", "validation": e,
                     "late": _edge(late, c["tf"], PRIMARY_HOLD) if late.height else {"n": 0},
                     "cost_scenarios": scen, "max_drawdown_r": Stt.drawdown_r(r[np.isfinite(r)])})
    ok = [r for r in rows if r["validation"].get("n", 0) >= MIN_N]
    for r, hp in zip(ok, Stt.holm(np.array([r["validation"]["p_edge"] for r in ok]))):
        r["holm_p"] = float(hp)
    for r in rows:
        v, lt = r["validation"], r["late"]
        if v.get("n", 0) < MIN_N:
            r["verdict"] = "too few validation trades"
        elif not (r["holm_p"] < ALPHA and v["edge"] > 0):
            r["verdict"] = "failed validation"
        elif r["entry"] == "market" and not (lt.get("n", 0) and lt["edge"] > 0 and lt["p_edge"] < ALPHA):
            r["verdict"] = "failed one-candle-delay check"
        elif v["mean_r"] > 0 and v["p_profit"] < ALPHA:
            r["verdict"] = "CONFIRMED: beats controls and profitable after spread"
        else:
            r["verdict"] = "beats controls, not profitable after spread"
    summary = {"symbol": symbol, "segment": "validation", "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "candidates_sha256": frozen["sha256"], "rows": rows}
    (out_dir(symbol) / "validation.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf8")
    return summary


def report_path(symbol: str):
    return REPO_ROOT / "docs" / "reports" / f"PATTERN_STUDY_{symbol}.md"
