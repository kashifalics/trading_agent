"""Experiment 7 Gann-only rules J1-J6 (spec 4.5): a Gann condition plus an objective price trigger, simulated on real bid/ask
with 1-minute resolution, against Experiment 5's matched random entries (same direction, risk bucket, session, volatility).

    J1  CHoCH on a candle inside an active whole-cycle window                    -> CHoCH direction
    J2  wick to a Square of Nine level, close >= 0.25 ATR back                    -> away from the level
    J3  the same at the 50% level of the latest major swing                       -> away from the level
    J4  close through the S_swing 1x1, retest within 10 candles closing back      -> break direction
    J5  J2-style rejection at a zone where 2+ price families overlap              -> away from the zone
    J6  liquidity sweep inside a seasonal window                                  -> sweep-reversal direction

Entry: next candle's open. Stop: one tick beyond the trigger's extreme (the simulator floors risk at 0.25 ATR). Primary exit:
2R, the stop or Experiment 5's HOLD, whichever first. TP1 (nearest Gann level >= 1R, else 1R) and TP3 (the next Gann level,
else 3R) are reported descriptively. One trade at a time per rule and direction.
"""
from datetime import datetime

import numpy as np
import polars as pl

from app.feature_engineering.indicators import atr as atr_fn
from app.gann import state as G
from app.gann.params import GannParams
from app.gold_research import controls as C
from app.gold_research import sim, study
from app.gold_research import stats as Stt
from app.gold_research.exp5 import run as R5
from app.gold_research.exp6 import stats as S6
from app.gold_research.exp7 import params as P
from app.gold_research.exp7 import timing as T
from app.gold_research.exp7.filters import PRICE_FAMILY, LineIndex
from app.historical.config import TF_SECONDS
from app.historical.split import load_split
from app.historical.store import load_m1
from app.market_data.bars import Bars
from app.market_structure.choch import detect_choch
from app.market_structure.liquidity import detect_liquidity_sweeps
from app.market_structure.swings import find_swings

PRIMARY_R, REJECT_ATR, RETEST = 2.0, 0.25, 10
ZONE_SETS = ("division", "square9", "angle_swing", "angle_atr", "symmetry")
TARGET_SETS = ("division", "square9", "symmetry", "angle_swing")


def rejection(c_prev: float, h: float, l: float, c: float, v: float, tol: float, atr: float) -> int:  # noqa: E741
    """+1: support rejection (came from above, wick into the level, closed >= 0.25 ATR above); -1: resistance; 0: none."""
    if c_prev > v and l <= v + tol and c >= v + REJECT_ATR * atr:
        return 1
    if c_prev < v and h >= v - tol and c <= v - REJECT_ATR * atr:
        return -1
    return 0


def zone_families(vals: dict, v: float, tol: float) -> set[str]:
    return {PRICE_FAMILY[m] for m, x in vals.items() if len(x) and np.any(np.abs(np.asarray(x) - v) <= tol)}


def retest_signals(c, h, l, line, lid, tol, window: int = RETEST) -> list[tuple[int, int]]:  # noqa: E741
    """A close through the line (same anchor on both candles), then the first candle within `window` that touches the line and
    closes back on the broken side."""
    out = []
    n = len(c)
    for i in range(1, n):
        if lid[i] < 0 or lid[i] != lid[i - 1] or not (np.isfinite(line[i]) and np.isfinite(line[i - 1])):
            continue
        s0, s1 = c[i - 1] - line[i - 1], c[i] - line[i]
        if s0 * s1 >= 0 or abs(s1) <= tol[i]:
            continue
        d = 1 if s1 > 0 else -1
        for j in range(i + 1, min(n, i + window + 1)):
            if lid[j] != lid[i]:
                break
            if l[j] <= line[j] + tol[j] and h[j] >= line[j] - tol[j] and np.sign(c[j] - line[j]) == d:
                out.append((j, d))
                break
    return out


def gate_events(events, mask: np.ndarray):
    return [e for e in events if 0 <= e.idx < len(mask) and mask[e.idx]]


def _one_x_one(b: Bars, p: GannParams) -> tuple[np.ndarray, np.ndarray]:
    """Per candle: the S_swing 1x1 line of the latest major anchor, and that anchor's index (-1: none)."""
    cx = G._context(b, p, False)
    n = len(b.c)
    line, lid = np.full(n, np.nan), np.full(n, -1, dtype=np.int64)
    bounds = sorted({0, n} | {min(max(s, 0), n) for _, s, _ in cx.spans} | {min(max(e, 0), n) for _, _, e in cx.spans})
    for x0, x1 in zip(bounds[:-1], bounds[1:]):
        A = [a for a, s, e in cx.spans if s <= x0 < e]
        if x0 >= x1 or not A:
            continue
        L = G._latest(A)
        s_ = G._scale(L, "swing", cx)
        if s_ is None:
            continue
        sign = 1.0 if L.kind == "low" else -1.0
        line[x0:x1] = L.price + sign * s_ * (np.arange(x0, x1) - L.idx)
        lid[x0:x1] = L.idx
    return line, lid


def signals(b: Bars, atr: np.ndarray, pn: pl.DataFrame, p: GannParams, lines: dict) -> dict[str, pl.DataFrame]:
    n = len(b.c)
    tick = p.tick
    tolp = np.where(np.isfinite(atr), np.maximum(p.price_tol_atr * atr, tick), np.nan)
    out = {r: [] for r in P.RULES}

    def add(rule, i, d, trig):
        stop = (b.l[i] - tick) if d > 0 else (b.h[i] + tick)
        out[rule].append((i, d, float(stop), float(trig)))

    swings = find_swings(b, 3, 3)
    for e in gate_events(detect_choch(b, swings), pn["t_cycle_bars"].to_numpy()):
        if np.isfinite(atr[e.idx]):
            d = 1 if e.direction == "bullish" else -1
            s = e.meta.get("swing_idx", e.idx) if e.meta else e.idx
            s = e.idx if s is None else s
            stop = (b.l[s:e.idx + 1].min() - tick) if d > 0 else (b.h[s:e.idx + 1].max() + tick)
            out["J1"].append((e.idx, d, float(stop), float(b.c[e.idx])))
    for e in gate_events(detect_liquidity_sweeps(b, swings), pn["t_seasonal"].to_numpy()):
        if np.isfinite(atr[e.idx]):
            d = 1 if e.direction == "bullish" else -1
            out["J6"].append((e.idx, d, float((e.low - tick) if d > 0 else (e.high + tick)), float(e.price)))
    ix = {m: LineIndex(lines[m]) for m in (*ZONE_SETS, "half") if m in lines}
    for i in range(1, n):
        a, t = atr[i], tolp[i]
        if not np.isfinite(a):
            continue
        vals = {m: x.values_at(i) for m, x in ix.items()}
        args = (b.c[i - 1], b.h[i], b.l[i], b.c[i])
        for rule, m in (("J2", "square9"), ("J3", "half")):
            for v in vals.get(m, ()):
                d = rejection(*args, float(v), t, a)
                if d:
                    add(rule, i, d, v)
                    break
        zone = {k: v for k, v in vals.items() if k in ZONE_SETS}
        done = False
        for m in ZONE_SETS:
            for v in zone.get(m, ()):
                d = rejection(*args, float(v), t, a)
                if d and len(zone_families(zone, float(v), t)) >= 2:
                    add("J5", i, d, v)
                    done = True
                    break
            if done:
                break
    line, lid = _one_x_one(b, p)
    for j, d in retest_signals(b.c, b.h, b.l, line, lid, np.nan_to_num(tolp, nan=np.inf)):
        if np.isfinite(atr[j]):
            add("J4", j, d, line[j])
    cols = {"idx": pl.Int64, "d": pl.Int64, "stop": pl.Float64, "trigger_px": pl.Float64}
    return {r: pl.DataFrame(sorted(v), schema=cols, orient="row") for r, v in out.items()}


def targets(entry: float, risk: float, d: int, levels: np.ndarray) -> tuple[float, float, bool]:
    """TP1: nearest Gann level at least 1R away in the trade direction (else 1R); TP3: the next Gann level beyond it (else 3R)."""
    r = np.sort(((np.asarray(levels, dtype=float) - entry) * d) / risk)
    r = r[r >= 1.0]
    if not len(r):
        return 1.0, 3.0, False
    return float(r[0]), float(r[1]) if len(r) > 1 else 3.0, True


def to_orders(sig: pl.DataFrame, atr: np.ndarray, n: int) -> sim.Orders:
    idx = sig["idx"].to_numpy()
    eb = idx + 1
    return sim.Orders(d=sig["d"].to_numpy().astype(np.int64), entry_bar=np.where(eb < n, eb, -1), stop=sig["stop"].to_numpy(),
                      atr=atr[idx])


def _one_at_a_time(idx: np.ndarray, d: np.ndarray, exit_bar: np.ndarray) -> np.ndarray:
    keep = np.zeros(len(idx), bool)
    busy: dict = {}
    for k in np.lexsort((idx, d)):
        if idx[k] >= busy.get(int(d[k]), -1):
            keep[k] = True
            busy[int(d[k])] = exit_bar[k]
    return keep


def _year_share(r: np.ndarray, ts: np.ndarray) -> float:
    yrs = ts.astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970
    by = [float(r[yrs == y].mean()) for y in np.unique(yrs) if (yrs == y).sum() >= P.FLOORS["min_year_trades"]]
    return sum(x > 0 for x in by) / len(by) if by else 0.0


def run(segment: str, draws: int, only: set | None = None, log=print) -> list[dict]:
    from app.gold_research.exp7.run import load

    rows = []
    p = GannParams()
    h = R5.HOLD
    for sym in P.SYMBOLS:
        for tf in P.RULE_TFS:
            ids = {r: f"J|{sym}|{tf}|{r}" for r in P.RULES}
            if only is not None and not any(i in only for i in ids.values()):
                continue
            df = load(sym, tf, segment).sort("ts")
            b = T.bars_from_frame(df, TF_SECONDS[tf])
            atr = atr_fn(b.h, b.l, b.c, p.atr_n)
            pn = G.panel(b, p, daily=tf == "D1")
            lines = T.line_sets(b, p)
            sigs = signals(b, atr, pn, p, lines)
            seg_start = 0 if segment == "train" else int(datetime.fromisoformat(load_split(sym)["validation"]["start"]).timestamp())
            S = sim.Series.from_frame(df, tf, load_m1(sym, upto=segment))
            pool = R5._pool(sym, tf, segment, S, atr, seg_start)
            pool_r = pool.select(*study.KEYS).with_columns(r=pl.Series(study._r(pool, PRIMARY_R, h)))
            tix = {m: LineIndex(lines[m]) for m in TARGET_SETS if m in lines}
            for rule in P.RULES:
                rid = ids[rule]
                if only is not None and rid not in only:
                    continue
                sg = sigs[rule].filter(pl.Series(b.t[sigs[rule]["idx"].to_numpy()] >= seg_start)) if sigs[rule].height else sigs[rule]
                row = {"id": rid, "family": "trading", "symbol": sym, "tf": tf, "method": rule, "track": "gann_only",
                       "signals": int(sg.height)}
                if sg.height == 0:
                    rows.append({**row, "status": "below floor", "trades": 0})
                    continue
                res = sim.simulate(S, to_orders(sg, atr, S.n), batch=6000, holds=(h,), hit_targets=(PRIMARY_R,))
                ok = res["simulated"].astype(bool)
                r_all = sim.r_multiple(res, PRIMARY_R, h)
                hit = res[f"hit_{PRIMARY_R:g}"]
                sb, fb = res["stop_bar"], res["fill_bar"]
                exit_bar = np.minimum(np.where((hit >= 0) & ((sb < 0) | (hit < sb)), hit, np.where(sb >= 0, sb, fb + h)), fb + h)
                keep = ok & _one_at_a_time(sg["idx"].to_numpy(), sg["d"].to_numpy(), np.where(ok, exit_bar, -1))
                if keep.sum() < P.FLOORS["rules_trades"]:
                    rows.append({**row, "status": "below floor", "trades": int(keep.sum())})
                    continue
                g = sg.filter(pl.Series(keep))
                r = r_all[keep]
                idx, d = g["idx"].to_numpy(), g["d"].to_numpy()
                Pp, R = res["entry_px"][keep], res["risk_px"][keep]
                fill_ts = np.where(res["fill_ts"][keep] > 0, res["fill_ts"][keep], S.t[idx])
                fbk = np.clip(fb[keep], 0, S.n - 1)
                spread = (S.ao[fbk] - S.bo[fbk]).astype(float)
                vol = C.vol_bucket(atr)
                t = pl.DataFrame({"entry": ["market"] * len(r), "direction": d, "risk_b": C.bucket(R / atr[idx], C.RISK_EDGES).astype(np.int8),
                                  "dist_b": np.full(len(r), -1, np.int8), "width_b": np.full(len(r), -1, np.int8),
                                  "session": C.session_ny(fill_ts), "vol": vol[idx], "period": C.period_key(fill_ts, segment),
                                  "segment": [segment] * len(r), "r": r, "entry_ts": fill_ts})
                t = t.cast({c: pool_r.schema[c] for c in study.KEYS if c in pool_r.schema})
                e = C.expectation(t, pool_r, "r")
                es = Stt.edge_stats(e["r"].to_numpy(), e["ctrl_mean"].to_numpy(), e["ctrl_var"].to_numpy(),
                                    e["ctrl_n"].to_numpy().astype(float), e["ctrl_cell"].to_numpy(), e["entry_ts"].to_numpy(),
                                    h * TF_SECONDS[tf])
                spread_r = spread / R
                m = R5.metrics(r, fill_ts, spread_r)
                tps = [targets(px, rk, int(dd), np.concatenate([tix[s].values_at(int(i)) for s in tix]) if tix else np.array([]))
                       for px, rk, dd, i in zip(Pp, R, d, idx)]
                tp1 = np.array([x[0] for x in tps])
                tp3 = np.array([x[1] for x in tps])
                fee = S6.cost_scenarios(r, spread, R, Pp)["r_fee"] if sym == "BTCUSDT" else None
                r2 = r - spread_r
                checks = {"mean_r_positive": bool(m["expectancy_r"] > 0), "positive_at_2x_costs": bool(r2.mean() > 0)}
                if segment == "train":
                    checks["positive_years_60pct"] = bool(_year_share(r, fill_ts) >= P.FLOORS["year_share"])
                rows.append({**row, "status": "tested", "trades": int(len(r)), "p": es.get("p_edge"),
                             "effect_ok": bool((es.get("edge") or 0) > 0), "edge": es.get("edge"), "edge_se": es.get("edge_se"),
                             "ctrl_mean_r": es.get("ctrl_mean_r"), "metrics": m, "checks": checks,
                             "mean_r_2x_costs": float(r2.mean()), "mean_r_fee": float(fee.mean()) if fee is not None else None,
                             "tp1_from_gann_share": float(np.mean([x[2] for x in tps])),
                             "tp1_r_mean": float(tp1.mean()), "tp3_r_mean": float(tp3.mean())})
            log(f"rules {sym} {tf}: " + ", ".join(f"{r}={sigs[r].height}" for r in P.RULES))
    return rows
