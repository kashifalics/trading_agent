"""Experiment 7 timing track (spec 4.3) and astro family (4.6): do Gann windows and levels coincide with reversals, volatility,
range expansion, direction changes or price reactions more often than random windows and levels covering the same share?

Outcomes use hindsight (that is what an outcome is); every window and level uses only what was known at its candle. Each row
is one registered test id; rows outside the tested families are labelled info or descriptive and can never pass.
"""
from datetime import datetime

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.feature_engineering.indicators import atr as atr_fn
from app.feature_engineering.indicators import true_range
from app.gann import state as G
from app.gann.params import GannParams
from app.gann.time_cycles import day_index, seasonal_mask, sq9_time_counts
from app.gold_research.events import bars_from_frame
from app.gold_research.exp7 import params as P
from app.gold_research.exp7 import stats as S
from app.gold_research.exp7.stats import (
    reactions,  # noqa: F401  (the plan's timing.reaction interface)
)
from app.historical.config import TF_SECONDS
from app.historical.split import load_split
from app.market_data.bars import Bars

DAY = 86400
FRACTAL, DCH_N, EXP_ATR = 10, 10, 1.5
LEVEL_HORIZON = 20
SQ4_CHUNK = 500
TWO_SIDED = {"reversal": False, "vol": False, "expansion": False, "dchange": True}


# ---- outcomes -----------------------------------------------------------------------------------------------------------------------
def outcomes(b: Bars, atr: np.ndarray) -> dict[str, np.ndarray]:
    n, k = len(b.c), FRACTAL
    rev = np.full(n, np.nan)
    if n > 2 * k:
        H, L = sliding_window_view(b.h, 2 * k + 1), sliding_window_view(b.l, 2 * k + 1)
        hi = (H[:, k] > H[:, :k].max(1)) & (H[:, k] > H[:, k + 1:].max(1))
        lo = (L[:, k] < L[:, :k].min(1)) & (L[:, k] < L[:, k + 1:].min(1))
        rev[k:n - k] = (hi | lo).astype(float)
    tr = true_range(b.h.copy(), b.l, b.c)
    prev = np.r_[np.nan, atr[:-1]]
    vol = tr / prev
    exp = np.where(np.isfinite(vol), (tr > EXP_ATR * prev).astype(float), np.nan)
    dch = np.full(n, np.nan)
    N = DCH_N
    if n > 2 * N:
        back = b.c[N:n - N] - b.c[:n - 2 * N]
        fwd = b.c[2 * N:] - b.c[N:n - N]
        ok = (back != 0) & (fwd != 0)
        dch[N:n - N] = np.where(ok, (np.sign(back) != np.sign(fwd)).astype(float), np.nan)
    return {"reversal": rev, "vol": vol, "expansion": exp, "dchange": dch}


# ---- window and line sets from the Gann engine -------------------------------------------------------------------------------------
def window_sets(b: Bars, p: GannParams, daily: bool) -> dict[str, S.WindowSet]:
    cx = G._context(b, p, daily)
    n = len(b.c)
    sets = {"t_cycle_bars": S.WindowSet.from_bar_counts(cx.spans, n, p.counts, None, p.tol_frac),
            "t_fraction": S.WindowSet.from_bar_counts(cx.spans, n, p.counts, p.fracs, p.tol_frac),
            "t_sq9_time": S.WindowSet.from_bar_counts(cx.spans, n, sq9_time_counts(p.sq9_time_max), None, p.tol_frac)}
    if daily:
        sets["t_cycle_days"] = S.WindowSet.from_bar_counts(cx.spans, n, p.counts, None, p.tol_frac, unit="day", bday=cx.bday)
    for col in ("t_anniversary", "t_balance_swing", "t_balance_atr", "t_balance_fixed"):
        ws = [w for w in cx.windows if w.column == col]
        if ws:
            anniv = col == "t_anniversary"
            sets[col] = S.WindowSet.from_windows(ws, "anniversary" if anniv else "jitter", cx.bday, n, p.tol_frac,
                                                 base=p.anniv_years if anniv else None)
    return sets


def seasonal_real(b: Bars, p: GannParams) -> np.ndarray:
    return seasonal_mask(b.t, p.seasonal_tol_days, p.seasonal)


def _doy_dates(doys) -> tuple:
    ref = np.datetime64("2001-01-01") + np.asarray(doys, dtype=np.int64) - 1
    return tuple((int(str(d)[5:7]), int(str(d)[8:10])) for d in ref)


def seasonal_controls(b: Bars, p: GannParams, draws: int, rng: np.random.Generator, target_cov: float):
    real = np.array([(np.datetime64(f"2001-{m:02d}-{d:02d}") - np.datetime64("2001-01-01")).astype(int) + 1 for m, d in p.seasonal])
    allowed = [x for x in range(1, 366) if np.min(np.minimum(np.abs(real - x), 365 - np.abs(real - x))) > p.seasonal_tol_days]
    for _ in range(draws):
        doys = list(rng.choice(allowed, size=len(real), replace=False))
        m = seasonal_mask(b.t, p.seasonal_tol_days, _doy_dates(doys))
        guard = 0
        while abs(m.mean() - target_cov) > S.COV_PP and guard < 8:
            if m.mean() > target_cov and len(doys) > 1:
                doys.pop(int(rng.integers(len(doys))))
            else:
                doys.append(int(rng.choice(allowed)))
            m, guard = seasonal_mask(b.t, p.seasonal_tol_days, _doy_dates(doys)), guard + 1
        yield m


def line_sets(b: Bars, p: GannParams) -> dict[str, S.LineSet]:
    cx = G._context(b, p, False)
    n = len(b.c)
    bounds = sorted({0, n} | {min(max(s, 0), n) for _, s, _ in cx.spans} | {min(max(e, 0), n) for _, _, e in cx.spans})
    stat = {"division": [], "twelfth": [], "square9": [], "symmetry": [], "half": []}
    x0s, x1s, ang = [], [], {"swing": [], "atr": []}
    rates = np.array(p.rates, dtype=float)
    order = np.argsort(rates)
    rgap = np.empty(len(rates))
    sr = rates[order]
    g = np.diff(sr)
    rgap[order] = np.r_[g, g[-1:]]
    for x0, x1 in zip(bounds[:-1], bounds[1:]):
        A = [a for a, s, e in cx.spans if s <= x0 < e]
        if x0 >= x1 or not A:
            continue
        L = G._latest(A)
        lv = G._static_levels(A, L, cx.prev.get(L), p)
        for m in stat:
            if m == "half":  # the 50% level of the latest major swing (Gann-only rule J3)
                stat[m].append(np.array([x["price"] for x in lv if x["method"] == "division" and x.get("fraction") == 0.5]))
            else:
                stat[m].append(np.array([x["price"] for x in lv if x["method"] == m]))
        x0s.append(x0)
        x1s.append(x1)
        for a in A:
            for kind in ("swing", "atr"):
                s_ = G._scale(a, kind, cx)
                if s_ is None:
                    continue
                sign = 1.0 if a.kind == "low" else -1.0
                k = len(rates)
                ang[kind].append((np.full(k, x0), np.full(k, x1), np.full(k, a.price), sign * rates * s_, np.full(k, a.idx),
                                  rgap * s_))
    out = {m: S.LineSet.static(np.array(x0s), np.array(x1s), stat[m]) for m in stat}
    for kind, parts in ang.items():
        if parts:
            x0, x1, p0, sl, ai, gs = (np.concatenate(v) for v in zip(*parts))
            out[f"angle_{kind}"] = S.LineSet(x0.astype(np.int64), x1.astype(np.int64), p0, sl, ai.astype(np.int64),
                                             np.zeros(len(p0)), gs)
    # Square of Four: absolute numbers (dollars), anchor-free; listed per chunk near that chunk's prices
    atr = cx.atr
    chunks_x0, chunks_x1, chunks_lv = [], [], []
    for x0 in range(0, n, SQ4_CHUNK):
        x1 = min(n, x0 + SQ4_CHUNK)
        pad = 5 * float(np.nanmax(atr[x0:x1])) if np.isfinite(atr[x0:x1]).any() else 0.0
        lo, hi = float(b.l[x0:x1].min()) - pad, float(b.h[x0:x1].max()) + pad
        lv = cx.sq4[(cx.sq4 >= lo) & (cx.sq4 <= hi)]
        chunks_x0.append(x0)
        chunks_x1.append(x1)
        chunks_lv.append(lv)
    out["sq4"] = S.LineSet.static(np.array(chunks_x0), np.array(chunks_x1), chunks_lv)
    return out


# ---- one series ---------------------------------------------------------------------------------------------------------------------
def status_for(inside: np.ndarray, y: np.ndarray, eval_mask: np.ndarray, p: GannParams) -> str:
    e = eval_mask & np.isfinite(y)
    if not e.any():
        return "below floor"
    if float(inside[e].mean()) > P.CONTROLS["coverage_rule"]:
        return "not testable: covers nearly every candle"
    yi = y[e][inside[e]]
    binary = bool(np.isin(np.unique(y[e]), (0.0, 1.0)).all())
    events = int((yi > 0).sum()) if binary else int(len(yi))
    if int(inside[e].sum()) < P.FLOORS["timing_inside_candles"] or events < P.FLOORS["timing_inside_events"]:
        return "below floor"
    return "tested"


def _multi(ys: dict, inside: np.ndarray, masks, eval_mask: np.ndarray, tail: str) -> dict:
    es = {o: eval_mask & np.isfinite(y) for o, y in ys.items()}
    real = {o: S.lift(ys[o][es[o]], inside[es[o]]) for o in ys}
    null = {o: [] for o in ys}
    for m in masks:
        for o in ys:
            null[o].append(S.lift(ys[o][es[o]], m[es[o]]))
    out = {}
    for o in ys:
        nl = np.array(null[o])
        pv = S.p_two_sided_log(real[o], nl, tail) if TWO_SIDED.get(o) else S.p_upper(real[o], nl, tail)
        out[o] = {"lift": real[o], "p": pv, "control_mean": float(np.nanmean(nl)) if np.isfinite(nl).any() else None,
                  "draws": len(nl)}
    return out


def run_series(b: Bars, symbol: str, tf: str, daily: bool, draws: int, seed: int, eval_mask: np.ndarray, methods=None,
               levels: bool = True, family: str = "timing", only: set | None = None, tail: str = "empirical",
               level_draws: int | None = None) -> list[dict]:
    p = GannParams()
    rng = np.random.default_rng(seed)
    atr = atr_fn(b.h, b.l, b.c, p.atr_n)
    Y = outcomes(b, atr)
    sets = window_sets(b, p, daily)
    n = len(b.c)
    rows = []
    for method, (col, tfs) in P.TIME_METHODS.items():
        if (methods is not None and method not in methods) or (methods is None and not (daily or col not in (
                "t_cycle_days", "t_balance_fixed"))):
            continue
        ids = {o: f"T|{symbol}|{tf}|{method}|{o}" for o in P.OUTCOMES}
        if only is not None and not any(i in only for i in ids.values()):
            continue
        if col == "t_seasonal":
            inside = seasonal_real(b, p)
        elif col in sets:
            ws = sets[col]
            inside = S.vmask(ws, ws.L, ws.W, n, ws.bday)
        else:
            inside = np.zeros(n, dtype=bool)
        e_all = eval_mask
        cov = float(inside[e_all].mean()) if e_all.any() else 0.0
        st = {o: status_for(inside, Y[o], eval_mask, p) for o in P.OUTCOMES}
        run_o = [o for o in P.OUTCOMES if st[o] == "tested" and (only is None or ids[o] in only)]
        res = {}
        if run_o:
            tc = float(inside.mean())
            masks = seasonal_controls(b, p, draws, rng, tc) if col == "t_seasonal" else \
                S.control_masks(sets[col], p, draws, rng, tc)
            res = _multi({o: Y[o] for o in run_o}, inside, masks, eval_mask, tail)
        for o in P.OUTCOMES:
            if only is not None and ids[o] not in only:
                continue
            ei = eval_mask & np.isfinite(Y[o])
            row = {"id": ids[o], "family": family, "symbol": symbol, "tf": tf, "method": method, "outcome": o,
                   "status": st[o] if family != "info" or st[o] != "tested" else "tested", "coverage": cov,
                   "n_inside": int(inside[ei].sum()), "events_inside": int(np.nansum(Y[o][ei & inside] > 0)),
                   "n": int(ei.sum())}
            if o in res:
                row.update(res[o])
                row["effect_ok"] = bool(np.isfinite(row["lift"]) and (row["lift"] > 1 or TWO_SIDED[o]))
                row["direction"] = "more" if row["lift"] > 1 else "less"
            rows.append(row)
    if levels:
        lt = P.CONTROLS["level_tail"] if (level_draws or draws) < P.DRAWS else tail
        rows += _level_rows(b, atr, symbol, tf, eval_mask, p, rng, level_draws or draws, only, lt)
    return rows


def _level_rows(b, atr, symbol, tf, eval_mask, p, rng, draws, only, tail) -> list[dict]:
    rows = []
    lines = line_sets(b, p)
    for m in (*P.LEVEL_METHODS, *P.DESCRIPTIVE_LEVELS):
        desc = m in P.DESCRIPTIVE_LEVELS
        rid = f"{'D' if desc else 'L'}|{symbol}|{tf}|{m}"
        if only is not None and rid not in only:
            continue
        ls = lines.get(m)
        row = {"id": rid, "family": "descriptive" if desc else "timing", "symbol": symbol, "tf": tf, "method": m,
               "outcome": "reaction"}
        if ls is None or not len(ls.p0):
            rows.append({**row, "status": "below floor", "touches": 0})
            continue
        res = S.level_test(b.h, b.l, b.c, atr, ls, eval_mask, p, draws, rng, LEVEL_HORIZON, tail)
        floor_ok = res["touches"] >= P.FLOORS["timing_inside_candles"] and res["reactions"] >= P.FLOORS["timing_inside_events"]
        status = ("descriptive" if desc else "tested") if floor_ok else "below floor"
        row.update(res)
        row.update({"status": status, "effect_ok": bool(np.isfinite(res["lift"]) and res["lift"] > 1)})
        rows.append(row)
    return rows


# ---- all instruments ----------------------------------------------------------------------------------------------------------------
def _eval_mask(symbol: str, t: np.ndarray, segment: str) -> np.ndarray:
    if segment == "train":
        return np.ones(len(t), dtype=bool)
    v0 = int(datetime.fromisoformat(load_split(symbol)["validation"]["start"]).timestamp())
    return t >= v0


def _bars(symbol: str, tf: str, segment: str) -> Bars:
    from app.gold_research.exp7.run import load

    return bars_from_frame(load(symbol, tf, segment), TF_SECONDS[tf])


def run_all(segment: str, draws: int, only: set | None = None, log=print, tail: str = "empirical",
            level_draws: int | None = None) -> list[dict]:
    rows = []
    for si, sym in enumerate(P.SYMBOLS):
        tfs = P.TIMING_TFS + (P.INFO_TFS if only is None else ())
        for ti, tf in enumerate(tfs):
            info = tf in P.INFO_TFS
            b = _bars(sym, tf, segment)
            methods = [m for m, (_, t) in P.TIME_METHODS.items() if (tf in t) or (info and "H1" in t)]
            r = run_series(b, sym, tf, daily=tf == "D1", draws=min(draws, 1000) if info else draws,
                           seed=P.CONTROLS["seed"] + 100 * si + ti, eval_mask=_eval_mask(sym, b.t, segment), methods=methods,
                           levels=not info, family="info" if info else "timing", only=only, tail=tail, level_draws=level_draws)
            rows += r
            log(f"timing {sym} {tf}: {len(r)} rows ({sum(x.get('status') == 'tested' for x in r)} tested)")
    return rows


def run_astro(segment: str, draws: int, only: set | None = None, log=print, tail: str = "empirical") -> list[dict]:
    from app.gann.astro import events as AE

    rows = []
    for si, sym in enumerate(P.SYMBOLS):
        ids = [f"A|{sym}|{e}|{o}" for e in P.ASTRO_EVENTS for o in P.ASTRO_OUTCOMES]
        if only is not None and not any(i in only for i in ids):
            continue
        b = _bars(sym, "D1", segment)
        p = GannParams()
        rng = np.random.default_rng(P.CONTROLS["seed"] + 1000 + si)
        atr = atr_fn(b.h, b.l, b.c, p.atr_n)
        Y = outcomes(b, atr)
        ev_mask = _eval_mask(sym, b.t, segment)
        t0, t1 = int(b.t[0]), int(b.t[-1]) + DAY
        events = {"moon_phase": [t for t, _ in AE.moon_phases(t0, t1)],
                  "mercury_station": [t for t, _ in AE.mercury_stations(t0, t1)],
                  "mars_jupiter": [t for t, _ in AE.aspects("mars", "jupiter", t0, t1, (0, 90, 180, 270))],
                  "mars_saturn": [t for t, _ in AE.aspects("mars", "saturn", t0, t1, (0, 90, 180, 270))]}
        bday = day_index(b.t)
        tol_days = P.ASTRO["window_days"]
        for ev, tss in events.items():
            inside = AE.event_mask(b.t, tss, tol_days)
            st = {o: status_for(inside, Y[o], ev_mask, p) for o in P.ASTRO_OUTCOMES}
            run_o = [o for o in P.ASTRO_OUTCOMES if st[o] == "tested" and (only is None or f"A|{sym}|{ev}|{o}" in only)]
            res = {}
            if run_o:
                masks = S.event_control_masks(len(b.t), bday, np.array([t // DAY for t in tss], dtype=np.int64), tol_days,
                                              draws, rng, float(inside.mean()), int(bday[0]), int(bday[-1]))
                res = _multi({o: Y[o] for o in run_o}, inside, masks, ev_mask, tail)
            for o in P.ASTRO_OUTCOMES:
                rid = f"A|{sym}|{ev}|{o}"
                if only is not None and rid not in only:
                    continue
                row = {"id": rid, "family": "astro", "symbol": sym, "tf": "D1", "method": ev, "outcome": o, "status": st[o],
                       "events": len(tss), "coverage": float(inside[ev_mask].mean())}
                if o in res:
                    row.update(res[o])
                    row["effect_ok"] = bool(np.isfinite(row["lift"]) and row["lift"] > 1)
                rows.append(row)
        log(f"astro {sym}: {len(events)} event types")
    return rows
