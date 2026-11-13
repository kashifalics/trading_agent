"""Experiment 5 (approved by the owner 2026-11-13): do strategy engine v2's six strategies have an edge after costs?
Plan: docs/engine_v2/EXPERIMENT_PLAN.md. The engine code itself is replayed candle by candle (TFData.at: no look-ahead, tested).

    python -m app.gold_research.exp5 gate     --symbol XAUUSD   events + counts only (no outcome) -> pre-registration (commit it)
    python -m app.gold_research.exp5 develop  --symbol XAUUSD   training segment: simulate, statistics, frozen development candidates
    python -m app.gold_research.exp5 validate --symbol XAUUSD   validation segment, ONLY the frozen candidates (refuses without them)

The sealed final test is never read: every load uses upto="train" or upto="validation" (store.load_tf refuses the test period).
"""
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone

import numpy as np
import polars as pl

from app.gold_research import controls as C
from app.gold_research import sim, study
from app.gold_research import stats as Stt
from app.gold_research.audit import cscv_pbo
from app.gold_research.events import bars_from_frame
from app.gold_research.exp2 import run as R2
from app.gold_research.exp4 import run as R4
from app.historical.config import DATA_ROOT, REPO_ROOT, TF_SECONDS
from app.historical.split import SPLIT_DIR, load_split
from app.historical.store import load_m1, load_tf
from app.price_action.engine import analyze_price_action
from app.strategy_engine.config import CHAINS, COMPATIBLE, ENGINE_VERSION, GROUPS
from app.strategy_engine.context import TFData
from app.strategy_engine.plan import build_plan
from app.strategy_engine.regime import Regime, classify
from app.strategy_engine.strategies import STRATEGIES

HIST = {"M5": "5m", "M15": "15m", "M30": "30m", "H1": "1H", "H4": "4H", "H8": "8H", "D1": "1D"}
TO_HIST = {**{v: k for k, v in HIST.items()}, "1W": "W1", "1M": "MN1"}
TFS = tuple(HIST)
HOLD, HOLD_SENS = 96, 48  # candles: the longest horizon the control pools store (section 9 of the pre-registration), 48 = sensitivity
GRID = tuple(round(0.5 + 0.1 * k, 1) for k in range(56))  # 0.5R .. 6.0R: first candle each is reached (exit timing)
N_MIN, FDR_Q, ALPHA, PF_MIN, YEAR_SHARE, DSR_MIN, PBO_MAX = 100, 0.10, 0.05, 1.2, 0.60, 0.95, 0.20
PRECISION = {"XAUUSD": 2, "EURUSD": 5, "GBPUSD": 5}
START = 220  # candles of warm-up before the first evaluation (indicators, 200-candle percentiles)
LIVE = ("READY", "WAITING FOR ENTRY")


def out_dir(symbol: str):
    return DATA_ROOT / "research" / symbol / "exp5"


def prereg_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp5_preregistration.json"


def dev_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp5_development.json"


def val_path(symbol: str):
    return SPLIT_DIR / f"{symbol}_exp5_validation.json"


def _sha(doc: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in doc.items() if k != "sha256"}, sort_keys=True, default=str).encode()).hexdigest()


def _git_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:  # noqa: BLE001 - provenance only
        return None


# ------------------------------------------------------------------ events: the engine replayed candle by candle (no outcomes)
def _close_ts(df: pl.DataFrame, tf: str) -> np.ndarray:
    return df["ts"].dt.epoch("s").to_numpy().astype(np.int64) + TF_SECONDS[tf]


def _levels(symbol: str, upto: str, close_ts: np.ndarray) -> dict[str, np.ndarray]:
    """Previous complete day / week high and low as known at each candle's close (the live engine's `levels`)."""
    out = {}
    for tf, (hk, lk, ek) in (("D1", ("pdh", "pdl", "pd_end")), ("W1", ("pwh", "pwl", None))):
        d = load_tf(symbol, tf, upto=upto).sort("ts")
        ce = _close_ts(d, tf)
        j = np.searchsorted(ce, close_ts, "right") - 1  # last daily / weekly candle closed by then
        ok = j >= 0
        jj = np.clip(j, 0, len(ce) - 1)
        out[hk] = np.where(ok, d["bid_high"].to_numpy()[jj], np.nan)
        out[lk] = np.where(ok, d["bid_low"].to_numpy()[jj], np.nan)
        if ek:
            out[ek] = np.where(ok, ce[jj], -1)
    return out


def _context(symbol: str, tf: str, upto: str, close_ts: np.ndarray) -> list[Regime | None]:
    """The context timeframe's regime as known at each signal candle's close (its last closed candle)."""
    ctx = CHAINS[HIST[tf]].context
    if ctx is None:
        return [None] * len(close_ts)
    htf = TO_HIST[ctx]
    d = load_tf(symbol, htf, upto=upto).sort("ts")
    t = TFData.build(ctx, bars_from_frame(d, TF_SECONDS[htf]))
    regs = [classify(t.at(k)) for k in range(t.n)]
    ce = _close_ts(d, htf)
    j = np.searchsorted(ce, close_ts, "right") - 1
    return [regs[k] if k >= 0 else None for k in j]


def events(symbol: str, tf: str, upto: str, log=print) -> pl.DataFrame:
    """Every live plan the engine would have shown at each candle close (ready = market at the next open; pending limit = limit
    order), plus the same strategies run outside their compatible regimes (descriptive only, section 7)."""
    eng = HIST[tf]
    df = load_tf(symbol, tf, upto=upto).sort("ts")
    b = bars_from_frame(df, TF_SECONDS[tf])
    t = TFData.build(eng, b, analyze_price_action(b))
    close_ts = _close_ts(df, tf)
    lv = _levels(symbol, upto, close_ts)
    ctx = _context(symbol, tf, upto, close_ts)
    spread = (df["ask_close"] - df["bid_close"]).to_numpy()
    group = GROUPS[CHAINS[eng].group]
    prec = PRECISION[symbol]
    rows, seen = [], set()
    for i in range(START, t.n - 1):
        levels = {k: (float(v[i]) if np.isfinite(v[i]) else None) for k, v in lv.items()}
        v = t.at(i, levels=levels)
        reg = classify(v)
        if reg.subtype == "insufficient_data":
            continue
        compat = set(COMPATIBLE.get(reg.label, ()))
        for key, strat in STRATEGIES.items():
            for d in (1, -1):
                c = strat.evaluate(v, reg, ctx[i], d)
                if not (c.status == "ready" or (c.status == "pending" and c.entry_mode == "limit")):
                    continue
                sig = (key, d, c.signal_idx, c.entry_mode, round(c.entry or 0, 8))
                if sig in seen:  # the same pending setup shown again on the next candle is one signal, as in the live lifecycle
                    continue
                plan, _ = build_plan(c, v, group=group, precision=prec, spread=float(spread[i]), price_now=None)
                if plan is None or plan["entry_status"] not in LIVE:
                    continue
                seen.add(sig)
                tg = plan["targets"]
                rows.append({"idx": i, "strategy": key, "direction": d, "entry_mode": plan["entry_mode"], "limit": plan["entry"],
                             "stop": plan["stop_loss"], "cancel": c.invalidation, "tp1": tg[0]["price"], "tp2": tg[1]["price"],
                             "tp3": tg[2]["price"], "plan_rr": plan["risk_reward"], "risk_atr": plan["risk_atr"], "regime": reg.label,
                             "context": ctx[i].label if ctx[i] is not None else "UNAVAILABLE", "compatible": key in compat
                             and reg.label != "HIGH_VOLATILITY", "signal_ts": int(close_ts[i])})
        if i % 50_000 == 0:
            log(f"{symbol} {tf} {upto}: candle {i:,}/{t.n:,}, {len(rows):,} signals")
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema={"idx": pl.Int64})


# ------------------------------------------------------------------ 1. gate: counts only, then the frozen pre-registration
def gate(symbol: str, log=print) -> dict:
    p = prereg_path(symbol)
    if p.exists():
        log(f"{p.name} exists: not overwritten")
        return json.loads(p.read_text())
    split = load_split(symbol)
    o = out_dir(symbol)
    o.mkdir(parents=True, exist_ok=True)
    tests = []
    train_end = int(datetime.fromisoformat(split["train"]["end_exclusive"]).timestamp())
    for tf in TFS:
        ep = o / f"events_{tf}.parquet"
        if ep.exists():  # written by `events` (possibly in parallel processes); signals only, no outcome
            ev = pl.read_parquet(ep)
        else:
            ev = events(symbol, tf, "validation", log)  # train + validation candles; outcomes are not computed here
            ev.write_parquet(ep, compression="zstd")
        if ev.height == 0:
            continue
        dev = ev.filter(pl.col("compatible") & (pl.col("signal_ts") < train_end))
        for key in STRATEGIES:
            for d, side in ((1, "long"), (-1, "short")):
                n = dev.filter((pl.col("strategy") == key) & (pl.col("direction") == d)).height
                tests.append({"tf": tf, "strategy": key, "direction": side, "signals": n,
                              "status": "run" if n >= N_MIN else f"not testable (fewer than {N_MIN} development signals)"})
        log(f"{tf}: {ev.height:,} signals ({dev.height:,} compatible, development)")
    doc = {"symbol": symbol, "experiment": 5, "approved": "owner, 2026-11-13 (final master execution)", "plan": "docs/engine_v2/EXPERIMENT_PLAN.md",
           "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code_commit": _git_head(), "engine_version": ENGINE_VERSION,
           "split_sha256": split["sha256"], "segments": {"development": "train", "confirmation": "validation", "sealed": "test (never read)"},
           "tests": tests, "criteria": {
               "development": [f">= {N_MIN} trades", "mean R after real bid/ask > 0", f"edge over matched random entries > 0 with BH q < {FDR_Q}",
                               f"mean R > 0 in >= {YEAR_SHARE:.0%} of development years", "mean R > 0 without the best year",
                               "mean R > 0 at 2x the spread", f"deflated Sharpe >= {DSR_MIN} counting all trials (experiments 1-5)",
                               f"CSCV probability of backtest overfitting <= {PBO_MAX} over the tested cells"],
               "validation": [f">= {N_MIN} trades", "mean R > 0 with the 95% cluster-robust CI (weekly clusters) above 0",
                              f"profit factor >= {PF_MIN}", "edge over matched random entries with Holm-adjusted p < 0.05 across the carried cells"]},
           "settings_fixed_before_outcomes": {
               "entries": "the engine's READY plans enter at the next candle's open (ask to buy, bid to sell); pending LIMIT plans are limit "
                          "orders that fill only when price trades 1 tick through, cancelled by a close beyond the invalidation, waiting the "
                          "group's expiry; pending STOP entries (strategies A and C) are not simulated as orders: the engine re-detects them "
                          "as READY at the close beyond the trigger, which is simulated (a slightly worse price than an intrabar stop fill)",
               "stop": "the plan's stop (invalidation + 0.1 ATR + the candle's spread), checked on bid/ask 1-minute paths, stop first inside a minute",
               "target": "TP1 only, full position, measured at its R from the actual fill rounded DOWN to 0.1R (conservative); partial exits descriptive",
               "horizon": f"{HOLD} candles (the longest horizon the control pools store) stands in for 'no time stop'; trades still open are "
                          f"valued at the close of candle {HOLD} and their share is reported; {HOLD_SENS} candles = sensitivity",
               "overlap": "one trade at a time per cell (strategy x direction x timeframe): a signal while the cell's previous trade is open is skipped",
               "controls": "the gold study's matched random-entry pools (same segment, entry type, risk or distance/width bucket, direction, "
                           "NY session, volatility, period); H8 pool built with the same builder",
               "walk_forward": "no parameter is fitted, so every development year is already out of sample: the walk-forward reduces to "
                               "the yearly breakdown",
               "ci_method": "cluster-robust SE with weekly clusters (the study's tested method) instead of a block bootstrap",
               "regime_usefulness": "the same strategies outside their compatible regimes are simulated for description only"}}
    doc["sha256"] = _sha(doc)
    p.write_text(json.dumps(doc, indent=1), encoding="utf8")
    log(f"pre-registration written: {p.name}, {sum(t['status'] == 'run' for t in tests)} of {len(tests)} cells testable")
    return doc


def load_prereg(symbol: str) -> dict:
    p = prereg_path(symbol)
    if not p.exists():
        raise RuntimeError("no experiment-5 pre-registration: run the gate and commit it first")
    d = json.loads(p.read_text())
    if _sha(d) != d["sha256"]:
        raise RuntimeError("experiment-5 pre-registration was edited after it was written")
    return d


# ------------------------------------------------------------------ 2. simulation of one timeframe and segment
def _pool(symbol: str, tf: str, segment: str, S: sim.Series, atr: np.ndarray, seg_start: int) -> pl.DataFrame:
    p = study.out_dir(symbol) / f"pool_{tf}_{segment}.parquet"
    if p.exists():
        return pl.read_parquet(p)
    rng = np.random.default_rng(sum(map(ord, f"{symbol}{tf}{segment}")))
    eligible = np.flatnonzero((S.t >= seg_start) & np.isfinite(atr) & (np.arange(S.n) + sim.HMAX + 2 < S.n))
    bars = np.sort(rng.choice(eligible, min(study.POOL_BARS, len(eligible)), replace=False))
    pool = C.pool(S, atr, C.vol_bucket(atr), bars, segment)
    pool.write_parquet(p, compression="zstd")
    return pool


def simulate(symbol: str, tf: str, segment: str, ev: pl.DataFrame, log=print) -> pl.DataFrame:
    """Outcomes of the given events (all from one segment) on real bid/ask with 1-minute resolution."""
    upto = "train" if segment == "train" else "validation"
    df = load_tf(symbol, tf, upto=upto).sort("ts")
    S = sim.Series.from_frame(df, tf, load_m1(symbol, upto=upto))
    b = bars_from_frame(df, TF_SECONDS[tf])
    from app.feature_engineering.indicators import atr as atr_fn
    atr = atr_fn(b.h, b.l, b.c, 14)
    split = load_split(symbol)
    seg_start = int(datetime.fromisoformat(split[segment]["start"]).timestamp()) if segment == "validation" else 0
    idx = ev["idx"].to_numpy()
    d = ev["direction"].to_numpy().astype(np.int64)
    lim = ev["entry_mode"].to_numpy() == "limit"
    tick = 10.0 ** -PRECISION[symbol]
    eb = idx + 1
    wait = np.array([GROUPS[CHAINS[HIST[tf]].group].pending_expiry_bars])[0]
    o = sim.Orders(d=d, entry_bar=np.where(eb < S.n, eb, -1), stop=ev["stop"].to_numpy(), atr=atr[idx],
                   limit=np.where(lim, ev["limit"].to_numpy(), np.nan), cancel=np.where(lim, ev["cancel"].to_numpy(), np.nan),
                   wait=int(wait), through=np.full(len(idx), tick))
    res = sim.simulate(S, o, batch=6000, holds=(HOLD_SENS, HOLD), hit_targets=GRID)
    late = sim.simulate(S, sim.Orders(d=d, entry_bar=np.where(eb + 1 < S.n, np.where(lim, -1, eb + 1), -1), stop=ev["stop"].to_numpy(),
                                      atr=atr[idx]), batch=6000, holds=(HOLD,))
    P, R = res["entry_px"], res["risk_px"]
    k = np.floor(np.where(np.isfinite(P), (ev["tp1"].to_numpy() - P) * d / R, np.nan) * 10 + 1e-9) / 10  # TP1 in R, rounded down
    fb = np.clip(res["fill_bar"], 0, S.n - 1)
    fill_ts = np.where(res["fill_ts"] > 0, res["fill_ts"], S.t[idx])
    vol = C.vol_bucket(atr)
    close = S.bc[idx]
    dist = np.abs(close - ev["limit"].to_numpy()) / atr[idx]
    width = np.abs(ev["limit"].to_numpy() - ev["cancel"].to_numpy()) / atr[idx]
    tr = ev.with_columns(
        entry=pl.Series(np.where(lim, "limit", "market")), fill_bar=pl.Series(res["fill_bar"]), entry_ts=pl.Series(fill_ts),
        entry_px=pl.Series(P), risk_px=pl.Series(R), k=pl.Series(k), simulated=pl.Series(res["simulated"]),
        stop_r=pl.Series(res["stop_r"]), stop_bar=pl.Series(res["stop_bar"]),
        risk_b=pl.Series(np.where(lim, -1, C.bucket(R / atr[idx], C.RISK_EDGES)).astype(np.int8)),
        dist_b=pl.Series(np.where(lim, C.bucket(dist, C.DIST_EDGES), -1).astype(np.int8)),
        width_b=pl.Series(np.where(lim, C.bucket(width, C.WIDTH_EDGES), -1).astype(np.int8)),
        session=pl.Series(C.session_ny(fill_ts)), vol=pl.Series(vol[idx]), period=pl.Series(C.period_key(fill_ts, segment)),
        segment=pl.lit(segment), spread_entry=pl.Series((S.ao[fb] - S.bo[fb]).astype(np.float32)),
        **{f"{c}_{h}": pl.Series(res[f"{c}_{h}"]) for h in (HOLD_SENS, HOLD) for c in ("mfe", "mfe_opt", "stopped", "end_r")},
        late_mfe=pl.Series(late[f"mfe_{HOLD}"]), late_stopped=pl.Series(late[f"stopped_{HOLD}"]), late_end=pl.Series(late[f"end_r_{HOLD}"]),
        late_stop_r=pl.Series(late["stop_r"]), late_sim=pl.Series(late["simulated"]),
        **{f"hit_{g:g}": pl.Series(res[f"hit_{g:g}"]) for g in GRID})
    tr = tr.filter(pl.col("simulated") & (pl.col("k") > 0) & (pl.col("entry_ts") >= seg_start))
    # one trade at a time per cell: exit bar = stop, TP1 (first candle at its R), or the horizon
    keep = np.zeros(tr.height, bool)
    hit = {g: tr[f"hit_{g:g}"].to_numpy() for g in GRID}
    kk, sb, fbar = tr["k"].to_numpy(), tr["stop_bar"].to_numpy(), tr["fill_bar"].to_numpy()
    tp_bar = np.array([hit.get(round(min(max(x, 0.5), 6.0), 1), np.full(tr.height, -1))[n] if np.isfinite(x) else -1 for n, x in enumerate(kk)])
    exit_bar = np.where((tp_bar >= 0) & ((sb < 0) | (tp_bar < sb)), tp_bar, np.where(sb >= 0, sb, fbar + HOLD))
    exit_bar = np.minimum(exit_bar, fbar + HOLD)
    order = np.lexsort((tr["idx"].to_numpy(), tr["direction"].to_numpy(), tr["strategy"].to_numpy()))
    busy: dict = {}
    for n in order:
        cell = (tr["strategy"][int(n)], int(tr["direction"][int(n)]), bool(tr["compatible"][int(n)]))
        if tr["idx"][int(n)] >= busy.get(cell, -1):
            keep[n] = True
            busy[cell] = exit_bar[n]
    tr = tr.with_columns(exit_bar=pl.Series(exit_bar))
    tr = tr.filter(pl.Series(keep)).drop([f"hit_{g:g}" for g in GRID])
    out_dir(symbol).mkdir(parents=True, exist_ok=True)
    tr.write_parquet(out_dir(symbol) / f"trades_{tf}_{segment}.parquet", compression="zstd")
    _pool(symbol, tf, segment, S, atr, seg_start)
    log(f"{symbol} {tf} {segment}: {ev.height:,} signals -> {tr.height:,} trades (one at a time per cell)")
    return tr


# ------------------------------------------------------------------ 3. statistics
def r_of(tr: pl.DataFrame, h: int = HOLD, optimistic: bool = False) -> np.ndarray:
    k = tr["k"].to_numpy()
    mfe = tr[f"mfe_opt_{h}" if optimistic else f"mfe_{h}"].to_numpy()
    return np.where(mfe >= k, k, np.where(tr[f"stopped_{h}"].to_numpy(), tr["stop_r"].to_numpy(), tr[f"end_r_{h}"].to_numpy()))


def with_controls(tr: pl.DataFrame, pool: pl.DataFrame, h: int = HOLD) -> pl.DataFrame:
    """Each trade against random entries of its stratum, both scored at the trade's own TP1 (k) and horizon h."""
    parts = []
    for kv in sorted(set(tr["k"].to_list())):
        t = tr.filter(pl.col("k") == kv)
        tt = t.select(*study.KEYS, "entry_ts", "risk_px", "spread_entry", "signal_ts", "regime", "context").with_columns(r=pl.Series(r_of(t, h)))
        p = pool.select(*study.KEYS).with_columns(r=pl.Series(study._r(pool, kv, h)))
        parts.append(C.expectation(tt, p, "r"))
    return pl.concat(parts) if parts else tr.head(0)


def metrics(r: np.ndarray, ts: np.ndarray, spread_r: np.ndarray) -> dict:
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return {"trades": 0}
    w, lo = r[r > 0], r[r <= 0]
    years = (ts.astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970)
    by_year = {int(y): float(np.mean(r[years == y])) for y in np.unique(years)}
    pos_years = sum(v > 0 for v in by_year.values()) / max(len(by_year), 1)
    best = max(by_year, key=by_year.get) if by_year else None
    wo_best = float(np.mean(r[years != best])) if best is not None and (years != best).any() else float("nan")
    dd = Stt.drawdown_r(r)
    sd = float(np.std(r, ddof=1)) if len(r) > 1 else float("nan")
    down = float(np.sqrt(np.mean(np.minimum(r, 0) ** 2))) if len(r) else float("nan")
    return {"trades": int(len(r)), "win_rate": float(len(w) / len(r)), "avg_win_r": float(w.mean()) if len(w) else None,
            "avg_loss_r": float(lo.mean()) if len(lo) else None, "expectancy_r": float(r.mean()), "total_r": float(r.sum()),
            "profit_factor": float(w.sum() / -lo.sum()) if lo.sum() < 0 else None, "sharpe_per_trade": float(r.mean() / sd) if sd > 0 else None,
            "sortino_per_trade": float(r.mean() / down) if down > 0 else None, "max_drawdown_r": float(dd),
            "recovery_factor": float(r.sum() / dd) if dd > 0 else None, "by_year": by_year, "positive_year_share": float(pos_years),
            "without_best_year": wo_best, "at_2x_spread": float(np.mean(r - spread_r[:len(r)])) if len(spread_r) else None}


def _cell_stats(g: pl.DataFrame, tf: str, h: int) -> dict:
    e = study._edge(g, tf, h)
    r = g["r"].to_numpy()
    ts = g["entry_ts"].to_numpy()
    spread_r = (g["spread_entry"] / g["risk_px"]).to_numpy()
    m = metrics(r, ts, spread_r)
    cl = Stt.cluster_ids(ts, h * TF_SECONDS[tf])
    cm = Stt.clustered_mean(r[np.isfinite(r)], cl[np.isfinite(r)])
    m["ci95"] = [cm["mean"] - 1.96 * cm["se"], cm["mean"] + 1.96 * cm["se"]] if math.isfinite(cm.get("se", float("nan"))) else None
    m["edge"], m["p_edge"], m["p_profit"] = e.get("edge"), e.get("p_edge", 1.0), e.get("p_profit", 1.0)
    m["ctrl_mean_r"] = e.get("ctrl_mean_r")
    m["by_regime"] = {k: float(v) for k, v in g.group_by("regime").agg(pl.col("r").mean()).iter_rows()}
    return m


def prior_trials(symbol: str) -> tuple[dict, list[float]]:
    counts, inv = R4.prior_trials(symbol)
    p4 = R4.result_path(symbol)
    if p4.exists():
        rows = [r for r in json.loads(p4.read_text())["rows"] if r.get("trades")]
        inv += [1.0 / max(r["trades"], 2) for r in rows]
        counts["experiment 4"] = len(rows)
    return counts, inv


def develop(symbol: str, log=print) -> dict:
    pre = load_prereg(symbol)
    split = load_split(symbol)
    train_end = int(datetime.fromisoformat(split["train"]["end_exclusive"]).timestamp())
    rows, desc = [], []
    for tf in TFS:
        p = out_dir(symbol) / f"events_{tf}.parquet"
        if not p.exists():
            continue
        ev = pl.read_parquet(p)
        if ev.height == 0:
            continue
        tr = simulate(symbol, tf, "train", ev.filter(pl.col("signal_ts") < train_end), log)
        pool = pl.read_parquet(study.out_dir(symbol) / f"pool_{tf}_train.parquet")
        for t in [x for x in pre["tests"] if x["tf"] == tf]:
            d = 1 if t["direction"] == "long" else -1
            sub = tr.filter((pl.col("strategy") == t["strategy"]) & (pl.col("direction") == d))
            comp, incomp = sub.filter(pl.col("compatible")), sub.filter(~pl.col("compatible"))
            row = {"tf": tf, "strategy": t["strategy"], "direction": t["direction"], "status_gate": t["status"]}
            if t["status"] == "run" and comp.height:
                g = with_controls(comp, pool)
                row.update(_cell_stats(g, tf, HOLD))
                g48 = with_controls(comp, pool, HOLD_SENS)
                row["hold_48"] = {"expectancy_r": float(np.nanmean(g48["r"].to_numpy()))}
                row["optimistic_expectancy_r"] = float(np.nanmean(r_of(comp, HOLD, optimistic=True)))
                row["open_at_horizon_share"] = float(np.mean((comp["mfe_96"].to_numpy() < comp["k"].to_numpy()) & ~comp["stopped_96"].to_numpy()))
                lr = np.where(comp["late_mfe"].to_numpy() >= comp["k"].to_numpy(), comp["k"].to_numpy(),
                              np.where(comp["late_stopped"].to_numpy(), comp["late_stop_r"].to_numpy(), comp["late_end"].to_numpy()))
                row["late_entry_expectancy_r"] = float(np.nanmean(np.where(comp["late_sim"].to_numpy(), lr, np.nan)))
                row["_r"] = g["r"].to_numpy()
                row["_ts"] = g["entry_ts"].to_numpy()
                rows.append(row)
            if incomp.height:
                desc.append({"tf": tf, "strategy": t["strategy"], "direction": t["direction"], "outside_regime_trades": incomp.height,
                             "outside_regime_expectancy_r": float(np.nanmean(r_of(incomp)))})
        log(f"{symbol} {tf}: development statistics done")
    counts, inv = prior_trials(symbol)
    n_trials = len(inv) + len(rows)
    null_var = float(np.mean(inv + [1.0 / max(r["trades"], 2) for r in rows])) if rows else 1.0
    qs = Stt.bh(np.array([r["p_edge"] for r in rows])) if rows else []
    # CSCV over the tested cells: yearly blocks of each cell's mean R
    years = sorted({int(y) for r in rows for y in r["by_year"]})
    pbo = None
    if rows and len(years) >= 12:
        sums = np.zeros((len(years), len(rows)))
        cnts = np.zeros((len(years), len(rows)))
        for j, r in enumerate(rows):
            yy = r["_ts"].astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970
            for i_, y in enumerate(years):
                m = yy == y
                sums[i_, j], cnts[i_, j] = float(np.nansum(r["_r"][m])), float(m.sum())
        pbo = cscv_pbo(sums, cnts)
    pbo_val = (pbo or {}).get("pbo")
    cands = []
    for r, q in zip(rows, qs):
        r["q"] = float(q)
        r["deflated_sharpe"] = R2.deflated_sharpe(r.pop("_r"), n_trials, null_var)
        r.pop("_ts", None)
        r["checks"] = {"enough_trades": r["trades"] >= N_MIN, "mean_r_gt_0": r["expectancy_r"] > 0,
                       "edge_gt_0_bh_q": (r["edge"] or -1) > 0 and r["q"] < FDR_Q, "positive_years_60pct": r["positive_year_share"] >= YEAR_SHARE,
                       "positive_without_best_year": (r["without_best_year"] or -1) > 0, "positive_at_2x_spread": (r["at_2x_spread"] or -1) > 0,
                       "deflated_sharpe": r["deflated_sharpe"] >= DSR_MIN, "pbo": pbo_val is not None and pbo_val <= PBO_MAX}
        r["status"] = "development candidate" if all(r["checks"].values()) else "failed"
        if r["status"] == "development candidate":
            cands.append({"tf": r["tf"], "strategy": r["strategy"], "direction": r["direction"]})
    out = {"symbol": symbol, "experiment": 5, "stage": "development", "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "preregistration_sha256": pre["sha256"], "tests_run": len(rows), "trials_counted_for_deflated_sharpe": n_trials, "prior_trials": counts,
           "pbo": pbo, "candidates": cands, "rows": rows, "outside_regime": desc}
    out["sha256"] = _sha(out)
    dev_path(symbol).write_text(json.dumps(out, indent=1, default=float), encoding="utf8")
    log(f"{symbol}: {len(rows)} cells tested, {len(cands)} development candidates")
    return out


def validate(symbol: str, log=print) -> dict:
    """Confirmation run on the validation segment, for the frozen development candidates only."""
    p = dev_path(symbol)
    if not p.exists():
        raise RuntimeError("no frozen development result: run develop first")
    dev = json.loads(p.read_text())
    if _sha(dev) != dev["sha256"]:
        raise RuntimeError("the development result was edited after it was written")
    split = load_split(symbol)
    v_start = int(datetime.fromisoformat(split["validation"]["start"]).timestamp())
    rows = []
    for tf in sorted({c["tf"] for c in dev["candidates"]}):
        ev = pl.read_parquet(out_dir(symbol) / f"events_{tf}.parquet").filter(pl.col("signal_ts") >= v_start)
        tr = simulate(symbol, tf, "validation", ev, log)
        pool = pl.read_parquet(study.out_dir(symbol) / f"pool_{tf}_validation.parquet")
        for c in [x for x in dev["candidates"] if x["tf"] == tf]:
            d = 1 if c["direction"] == "long" else -1
            sub = tr.filter((pl.col("strategy") == c["strategy"]) & (pl.col("direction") == d) & pl.col("compatible"))
            if sub.height == 0:
                rows.append({**c, "trades": 0})
                continue
            rows.append({**c, **_cell_stats(with_controls(sub, pool), tf, HOLD)})
    ps = np.array([r.get("p_edge", 1.0) for r in rows])
    adj = Stt.holm(ps) if len(rows) else []
    passed = []
    for r, a in zip(rows, adj):
        r["holm_p"] = float(a)
        ci = r.get("ci95")
        r["checks"] = {"enough_trades": r.get("trades", 0) >= N_MIN, "ci_above_0": bool(ci and ci[0] > 0),
                       "profit_factor": (r.get("profit_factor") or 0) >= PF_MIN, "holm_edge": (r.get("edge") or -1) > 0 and r["holm_p"] < ALPHA}
        r["status"] = "passed validation" if all(r["checks"].values()) else "failed validation"
        if r["status"] == "passed validation":
            passed.append({k: r[k] for k in ("tf", "strategy", "direction")})
    out = {"symbol": symbol, "experiment": 5, "stage": "validation", "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "development_sha256": dev["sha256"], "carried": len(rows), "passed": passed, "rows": rows,
           "note": "Passing validation is not 'validated' in the product: the plan requires the sealed final test (separate approval) and a "
                   "frozen paper forward test first."}
    val_path(symbol).write_text(json.dumps(out, indent=1, default=float), encoding="utf8")
    log(f"{symbol}: {len(rows)} candidates validated, {len(passed)} passed")
    return out
