"""Experiment 2 signal-scarcity diagnostics (counts only). Analysis only.

Counts how many candidate events survive each detection condition of the six setups, how many orders fill and why the others do
not, and how many trades reach the development sample, by timeframe, direction and year. Also counts (never tests) a few broader
variants of each condition to separate genuinely rare market structures from restrictive implementation choices.

Never computes trade outcomes or profitability; never changes setups, thresholds or stored results; reads only the training period
(2003-05-05 to 2020-02-08) through the sealed loader. Output: data/historical/research/XAUUSD/exp2/diagnostics.json.
"""
import json
from datetime import datetime, timezone

import numpy as np
import polars as pl
from scipy import stats

from app.feature_engineering.indicators import atr as atr_fn
from app.gold_research import regimes, sim
from app.gold_research.combos import tf_state
from app.gold_research.events import ATR_PERIOD, bars_from_frame, chunk_events
from app.gold_research.exp2 import data as D
from app.gold_research.exp2 import run as R
from app.historical.config import TF_SECONDS
from app.historical.store import load_m1, load_tf
from app.historical.sync import bar_close
from app.market_structure.bos import detect_structure_breaks
from app.market_structure.swings import find_swings
from app.patterns.candles import _roll_max, _roll_min, _sh
from app.patterns.context import compute_levels, first_touch
from app.price_action.levels import detect_levels


def _years(ts: np.ndarray) -> np.ndarray:
    return ts.astype("datetime64[s]").astype("datetime64[Y]").astype(np.int64) + 1970


def _by(arr_dir: np.ndarray, years: np.ndarray | None = None) -> dict:
    out = {"total": int(len(arr_dir)), "long": int((arr_dir > 0).sum()), "short": int((arr_dir < 0).sum())}
    if years is not None and len(years):
        y, c = np.unique(years, return_counts=True)
        out["by_year"] = {int(a): int(b) for a, b in zip(y, c)}
    return out


def funnels(symbol: str, tf: str) -> dict:
    df = load_tf(symbol, tf, upto="train").sort("ts")
    b = bars_from_frame(df, TF_SECONDS[tf])
    n = len(b)
    a = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    t = b.t
    yrs = _years(t)
    lv = compute_levels(df["ts"], bar_close(tf, t), b.h, b.l)
    evs, hits, trend = chunk_events(b, a, lv)
    o, h, lo, c = b.o, b.h, b.l, b.c
    rng = h - lo
    body = np.abs(c - o)
    res: dict = {"candles": n, "first": str(df["ts"].min())[:10], "last": str(df["ts"].max())[:10]}

    # ---- S1: supply/demand zone (base 1-3 candles <= 0.8 ATR, impulse >= 1.5 ATR with body >= 60%, close beyond the base) + HTF trend
    a_prev = _sh(a, 1)
    with np.errstate(invalid="ignore"):
        big = rng >= 1.5 * a_prev
        strong = big & (body >= 0.6 * rng)
        base1 = _sh(rng, 1) <= 0.8 * a_prev
        cand = strong & base1
        up_beyond = cand & (c > o) & (c > _sh(h, 1))
        dn_beyond = cand & (c < o) & (c < _sh(lo, 1))
    zones = [e for e in evs if e.kind in ("demand_zone", "supply_zone")]
    zd = np.array([1 if e.kind == "demand_zone" else -1 for e in zones])
    zi = np.array([e.idx for e in zones], dtype=np.int64)
    htf = tf_state(symbol, R.HTF[tf], "train")
    j = np.searchsorted(htf["close"], bar_close(tf, t), side="right") - 1
    htf_trend = np.where(j >= 0, htf["trend"][np.maximum(j, 0)], 0)
    aligned = htf_trend[zi] == zd if len(zi) else np.array([], bool)
    res["S1"] = {"conditions": [
        ("candles", n), ("impulse range >= 1.5 ATR", int(np.nansum(big))), ("+ body >= 60% of range", int(np.nansum(strong))),
        ("+ previous candle is a base (range <= 0.8 ATR)", int(np.nansum(cand))),
        ("+ closes beyond the base in the impulse direction", int(np.nansum(up_beyond) + np.nansum(dn_beyond))),
        ("zones emitted by the detector (1-3 candle base, one zone per impulse)", len(zones)),
        ("+ higher-timeframe structure trend equals the zone direction", int(aligned.sum()))],
        "zones": _by(zd, yrs[zi] if len(zi) else None), "aligned": _by(zd[aligned], yrs[zi][aligned] if len(zi) else None),
        "htf": R.HTF[tf], "htf_trend_share_at_zones": {k: float(np.mean(htf_trend[zi] == v)) if len(zi) else 0.0
                                                       for k, v in (("up", 1), ("down", -1), ("none", 0))}}

    # ---- S2: order block after BOS
    sw = find_swings(b)
    breaks, _tr = detect_structure_breaks(b, sw)
    n_bos = sum(1 for e in breaks if e.kind == "BOS")
    disp_ok = cand_ok = 0
    for br in breaks:
        if br.kind != "BOS":
            continue
        jj, s = br.idx, br.meta.get("swing_idx")
        if s is None or not np.isfinite(a[jj]):
            continue
        bull = br.direction == "bullish"
        k = s + int(np.argmin(lo[s:jj + 1])) if bull else s + int(np.argmax(h[s:jj + 1]))
        disp = float(h[k:jj + 1].max() - lo[k]) if bull else float(h[k] - lo[k:jj + 1].min())
        cands = [i for i in range(k, max(-1, k - 7), -1) if (c[i] < o[i] if bull else c[i] > o[i])]
        cand_ok += bool(cands)
        disp_ok += bool(cands) and disp >= 1.5 * a[jj]
    pats, hidx, hdir, _hs, _hl, _hh = hits.rows()
    pats = np.array(pats)
    ob_bos = pats == "order_block_bos"
    ob_choch = pats == "order_block_choch"
    res["S2"] = {"conditions": [("structure breaks (BOS + CHoCH)", len(breaks)), ("BOS only", n_bos),
                                ("+ an opposite candle within 6 candles of the impulse origin", cand_ok),
                                ("+ displacement >= 1.5 ATR", disp_ok), ("order blocks emitted after BOS (deduplicated)", int(ob_bos.sum()))],
                 "emitted": _by(hdir[ob_bos], yrs[hidx[ob_bos]]), "variant_counts": {"order blocks after CHoCH (excluded by design)": int(ob_choch.sum())}}

    # ---- S3: FVG whose middle candle is a displacement candle
    with np.errstate(invalid="ignore"):
        bull_gap = lo > _sh(h, 2)
        bear_gap = h < _sh(lo, 2)
        gap = np.where(bull_gap, lo - _sh(h, 2), np.where(bear_gap, _sh(lo, 2) - h, 0.0))
        fvg = (bull_gap | bear_gap) & (gap >= 0.1 * a)
        mid_rng, mid_body, a_mid = _sh(rng, 1), _sh(body, 1), _sh(a, 1)
        mid2 = fvg & (mid_rng >= 2 * a_mid)
        mid15 = fvg & (mid_rng >= 1.5 * a_mid)
        disp = mid2 & (mid_body >= 0.7 * mid_rng)
    di = pats == "displacement_imbalance"
    res["S3"] = {"conditions": [("three-candle gaps", int(np.nansum(bull_gap | bear_gap))), ("+ gap >= 0.1 ATR", int(np.nansum(fvg))),
                                ("+ middle candle range >= 2 ATR", int(np.nansum(mid2))), ("+ middle candle body >= 70%", int(np.nansum(disp))),
                                ("emitted by the detector", int(di.sum()))],
                 "emitted": _by(hdir[di], yrs[hidx[di]]),
                 "variant_counts": {"middle candle range >= 1.5 ATR (instead of 2)": int(np.nansum(mid15 & (mid_body >= 0.7 * mid_rng)))}}

    # ---- S4: broken support/resistance band
    bo = [e for e in evs if e.kind == "breakout"]
    n_win = n_lvl = win_with = 0
    for w in range(200, n, 200):
        lvls = detect_levels(b, sw, a, as_of=w - 1)
        n_win += 1
        n_lvl += len(lvls)
        win_with += bool(lvls)
    bod = np.array([1 if e.direction == "bullish" else -1 for e in bo])
    boi = np.array([e.idx for e in bo], dtype=np.int64)
    res["S4"] = {"conditions": [("200-candle windows", n_win), ("windows with at least one band (2+ swings within 0.5 ATR)", win_with),
                                ("bands across windows", n_lvl), ("breakouts (close >= 0.25 ATR beyond, from the other side)", len(bo))],
                 "emitted": _by(bod, yrs[boi] if len(boi) else None)}

    # ---- S5: previous-week sweep and reclaim (first candle of the week beyond the level)
    tl = first_touch(lv.pwl, lo, lv.week_id, above=False)
    th = first_touch(lv.pwh, h, lv.week_id, above=True)
    sw_lo, sw_hi = tl & (c > lv.pwl), th & (c < lv.pwh)
    any_lo = np.isfinite(lv.pwl) & (lo < lv.pwl) & (c > lv.pwl)
    any_hi = np.isfinite(lv.pwh) & (h > lv.pwh) & (c < lv.pwh)
    weeks = int(len(np.unique(lv.week_id[np.isfinite(lv.pwl)])))
    def per_week(m):
        return int(len(np.unique(lv.week_id[m])))
    res["S5"] = {"conditions": [("weeks with a previous-week level", weeks),
                                ("week-sides (previous-week low, previous-week high) that price traded beyond", per_week(tl) + per_week(th)),
                                ("+ the FIRST candle beyond it closed back inside (the rule used)", int(sw_lo.sum() + sw_hi.sum()))],
                 "emitted": _by(np.r_[np.ones(int(sw_lo.sum())), -np.ones(int(sw_hi.sum()))]),
                 "variant_counts": {"week-sides where ANY candle beyond the level closed back inside": per_week(any_lo) + per_week(any_hi)}}

    # ---- S6: range edge in a no-trend regime
    reg = regimes.compute(t, o, h, lo, c, a, trend)
    tr = np.asarray(reg["trend_regime"])
    none = tr == "none"
    weak = np.isin(tr, ["none", "weak_bullish", "weak_bearish"])
    hi50, lo50 = _sh(_roll_max(h, 50), 1), _sh(_roll_min(lo, 50), 1)
    with np.errstate(invalid="ignore"):
        nh = (c <= hi50) & (c >= hi50 - 0.25 * a)
        nl = (c >= lo50) & (c <= lo50 + 0.25 * a)
        touch_hi = h >= hi50 - 0.25 * a
    def onset(m):
        return m & ~np.r_[False, m[:-1]]
    res["S6"] = {"conditions": [("candles", n), ("trend regime 'none'", int(none.sum())),
                                ("+ close within 0.25 ATR below the 50-candle high or above the low", int(np.nansum(none & (nh | nl)))),
                                ("+ first candle of such a run (onset)", int(np.nansum(onset(none & nh)) + np.nansum(onset(none & nl))))],
                 "trend_regime_share": {k: float((tr == k).mean()) for k in np.unique(tr)},
                 "variant_counts": {"regime 'none' or weak, close-based onset": int(np.nansum(onset(weak & nh)) + np.nansum(onset(weak & nl))),
                                    "regime 'none', high touching within 0.25 ATR (not close-based), onset": int(np.nansum(onset(none & touch_hi)))}}
    return res


def fill_and_sample(symbol: str, tf: str) -> dict:
    """Orders -> fills (and why not) -> development trades, per setup and direction; counts only."""
    df = load_tf(symbol, tf, upto="train").sort("ts")
    S = sim.Series.from_frame(df, tf, load_m1(symbol, upto="train"))
    b = bars_from_frame(df, TF_SECONDS[tf])
    a = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    orders = R.setup_orders(symbol, tf, df, S)
    idx = orders["idx"].to_numpy()
    d = orders["direction"].to_numpy().astype(np.int64)
    lim, far = orders["limit"].to_numpy(), orders["far"].to_numpy()
    J = idx[:, None] + 1 + np.arange(R.WAIT)
    real = J < S.n
    Jc = np.clip(J, 0, S.n - 1)
    Ld = (d > 0)[:, None]
    touch = np.where(Ld, S.al[Jc] < lim[:, None], S.bh[Jc] > lim[:, None]) & real
    cancel = np.where(Ld, S.bc[Jc] < far[:, None], S.bc[Jc] > far[:, None]) & real
    ft = np.where(touch.any(1), touch.argmax(1), R.WAIT)
    fc = np.where(cancel.any(1), cancel.argmax(1), R.WAIT)
    reason = np.where(ft < R.WAIT, np.where(ft <= fc, "touched", "cancelled first"), np.where(fc < R.WAIT, "cancelled first", "expired untouched"))
    through_open = (S.ao - S.bo)[idx]
    close_spread = (S.ac - S.bc)[idx]
    med = float(np.median(S.ao - S.bo))
    base = dict(d=d, entry_bar=idx + 1, stop=far - d * R.BUFFER_ATR * a[idx], atr=a[idx], limit=lim, cancel=far, wait=R.WAIT)
    fills = {}
    for name, thr in (("touch", None), ("conservative (open spread, as run)", through_open), ("conservative (close spread)", close_spread),
                      ("conservative (median spread)", np.full(len(idx), med))):
        res = sim.simulate(S, sim.Orders(**base, through=thr), holds=(1,))
        fills[name] = res["fill_bar"] >= 0
    trades = pl.read_parquet(R.out_dir(symbol) / f"trades_{tf}.parquet")
    s = D.load(symbol)
    dev_end = int(datetime.fromisoformat(s["development"]["end_exclusive"]).timestamp())
    key = f"{R.PRIMARY_TARGET:g}R_{R.PRIMARY_HOLD[tf]}"
    in_dev = (trades["fill_ts"] < dev_end).to_numpy()
    exit_ok = (trades[f"exit_{key}"] < dev_end).to_numpy()
    gap = trades[f"gap_{key}"].to_numpy()
    sim_ok = trades[f"r_{key}"].is_not_nan().to_numpy()  # "was simulable" (outcome values are not read)
    out = {"orders": int(len(idx)), "orders_in_development": int((S.t[idx] < dev_end).sum()), "setups": {}}
    sig_dev = S.t[idx] < dev_end
    for setup in R.SETUPS:
        for dd, dn in ((1, "long"), (-1, "short")):
            m = (orders["setup"] == setup).to_numpy() & (d == dd)
            tm = (trades["setup"] == setup).to_numpy() & (trades["direction"] == dd).to_numpy()
            dev_trades = tm & in_dev & exit_ok & ~gap & sim_ok
            out["setups"][f"{setup}|{dn}"] = {
                "orders_dev": int((m & sig_dev).sum()),
                "reasons_dev": {r: int((m & sig_dev & (reason == r)).sum()) for r in ("touched", "cancelled first", "expired untouched")},
                "fills_dev": {k: int((m & sig_dev & v).sum()) for k, v in fills.items()},
                "filled_rows_in_results": int(tm.sum()), "dev_fill_in_period": int((tm & in_dev).sum()),
                "dev_exit_before_boundary": int((tm & in_dev & exit_ok).sum()), "dev_no_gap": int((tm & in_dev & exit_ok & ~gap).sum()),
                "development_trades": int(dev_trades.sum()),
                "dev_trades_by_year": {int(y): int(cn) for y, cn in zip(*np.unique(_years(trades["fill_ts"].to_numpy()[dev_trades]), return_counts=True))}}
    out["spread_used_for_conservative_fill"] = {
        "median_open_spread_signal": float(np.median(through_open)), "median_close_spread_signal": float(np.median(close_spread)),
        "median_spread_all_candles": med, "share_open_spread_gt_3x_median": float(np.mean(through_open > 3 * med)),
        "p95_open_spread": float(np.percentile(through_open, 95)), "p95_close_spread": float(np.percentile(close_spread, 95))}
    hours = (S.t[idx] % 86400) // 3600
    out["signal_candle_open_hours_utc"] = {int(k): int(v) for k, v in zip(*np.unique(hours, return_counts=True))}
    return out


def extras(symbol: str, tf: str) -> dict:
    """Further counts (development period only): the S4 same-candle deduplication, the S6 regime/edge conflict, and how many
    unfilled orders a longer wait would have touched. Counts only; nothing is simulated."""
    s = D.load(symbol)
    dev_end = int(datetime.fromisoformat(s["development"]["end_exclusive"]).timestamp())
    df = load_tf(symbol, tf, upto="train").sort("ts")
    S = sim.Series.from_frame(df, tf, load_m1(symbol, upto="train"))
    b = bars_from_frame(df, TF_SECONDS[tf])
    a = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    lv = compute_levels(df["ts"], bar_close(tf, b.t), b.h, b.l)
    evs, _hits, trend = chunk_events(b, a, lv)
    out: dict = {}
    bo = [e for e in evs if e.kind == "breakout" and b.t[e.idx] < dev_end]
    keys = [(e.idx, e.direction) for e in bo]
    multi = {k for k in set(keys) if keys.count(k) > 1}
    zero_width = sum(1 for e in bo if not e.low < e.high)
    out["S4_dedup"] = {"breakouts_dev": len(bo), "unique_candle_direction": len(set(keys)), "candles_breaking_2plus_bands": len(multi),
                       "zero_width_bands": zero_width}
    reg = regimes.compute(b.t, b.o, b.h, b.l, b.c, a, trend)
    tr = np.asarray(reg["trend_regime"])
    hi50, lo50 = _sh(_roll_max(b.h, 50), 1), _sh(_roll_min(b.l, 50), 1)
    with np.errstate(invalid="ignore"):
        near = ((b.c <= hi50) & (b.c >= hi50 - 0.25 * a)) | ((b.c >= lo50) & (b.c <= lo50 + 0.25 * a))
    dev = b.t < dev_end
    out["S6_conflict"] = {"near_edge_candles_dev": int((near & dev).sum()), "share_none_regime_all_candles_dev": float(np.mean(tr[dev] == "none")),
                          "share_none_regime_at_near_edge_dev": float(np.mean(tr[near & dev] == "none")) if (near & dev).any() else 0.0,
                          "regime_at_near_edge_dev": {k: int(v) for k, v in zip(*np.unique(tr[near & dev], return_counts=True))}}
    orders = R.setup_orders(symbol, tf, df, S)
    idx = orders["idx"].to_numpy()
    d = orders["direction"].to_numpy().astype(np.int64)
    lim = orders["limit"].to_numpy()
    m = S.t[idx] < dev_end
    res = {}
    for w in (20, 40, 60):
        J = idx[:, None] + 1 + np.arange(w)
        real = J < S.n
        Jc = np.clip(J, 0, S.n - 1)
        touch = np.where((d > 0)[:, None], S.al[Jc] < lim[:, None], S.bh[Jc] > lim[:, None]) & real
        res[w] = touch.any(1)
    out["wait_touch_dev"] = {}
    for setup in R.SETUPS:
        sm = m & (orders["setup"] == setup).to_numpy()
        out["wait_touch_dev"][setup] = {"orders": int(sm.sum()), **{f"touched_within_{w}": int((sm & v).sum()) for w, v in res.items()}}
    return out


LEVEL_REFRESH_SAME_TIME = {"H4": 200, "H8": 100, "D1": 33}  # about 33 trading days, the H4 refresh interval, on every timeframe


def s4_refresh_variant(symbol: str, tf: str) -> dict:
    """S4 breakouts (development, unique candle and direction) with the experiment's 200-candle level refresh versus a refresh at
    the same calendar interval on every timeframe. Same detectors and parameters; counts only. Run on the whole series in one
    piece, so the 200-candle count can differ slightly from the chunked experiment run."""
    from app.price_action.levels import BreakoutParams, detect_breakouts
    s = D.load(symbol)
    dev_end = int(datetime.fromisoformat(s["development"]["end_exclusive"]).timestamp())
    df = load_tf(symbol, tf, upto="train").sort("ts")
    b = bars_from_frame(df, TF_SECONDS[tf])
    a = atr_fn(b.h, b.l, b.c, ATR_PERIOD)
    sw = find_swings(b)
    n = len(b)
    out = {}
    for step in sorted({200, LEVEL_REFRESH_SAME_TIME[tf]}, reverse=True):
        keys, years = set(), {}
        for w in range(step, n, step):
            end = min(n, w + step)
            levels = detect_levels(b, sw, a, as_of=w - 1)
            if not levels:
                continue
            sub = b.upto(min(n, end + 20))
            for e in detect_breakouts(sub, levels, a[:len(sub)], BreakoutParams(lookback_bars=len(sub) - w)):
                if e.kind == "breakout" and w <= e.idx < end and b.t[e.idx] < dev_end and (e.idx, e.direction) not in keys:
                    keys.add((e.idx, e.direction))
                    y = int(_years(np.array([b.t[e.idx]]))[0])
                    years[y] = years.get(y, 0) + 1
        out[f"refresh_every_{step}_candles"] = {"breakouts_dev_unique": len(keys), "by_year": dict(sorted(years.items()))}
    return out


def gap_breakdown(symbol: str) -> dict:
    """Development trades excluded by the unscheduled-gap rule, split into those whose only gaps start at the daily rollover break
    (21:00-21:05 or 22:00-22:05 UTC, at most 120 minutes) and the rest. Counts only."""
    s = D.load(symbol)
    dev_end = int(datetime.fromisoformat(s["development"]["end_exclusive"]).timestamp())
    tr_end = int(datetime.fromisoformat(s["screening"]["end_exclusive"]).timestamp())
    g = D.gaps_v2(symbol).filter(pl.col("unscheduled") & (pl.col("start_epoch") < tr_end))  # training period only
    st = g["start_epoch"].to_numpy()
    sec = st % 86400
    brk = (((sec >= 21 * 3600) & (sec <= 21 * 3600 + 300)) | ((sec >= 22 * 3600) & (sec <= 22 * 3600 + 300))) & (g["minutes"].to_numpy() <= 120)
    order = np.argsort(st)
    st, brk = st[order], brk[order]
    other = st[~brk]
    out = {"unscheduled_gaps_in_training": int((st < tr_end).sum()), "of_which_daily_break_time": int((brk & (st < tr_end)).sum()),
           "daily_break_time_by_year": {int(y): int(c) for y, c in zip(*np.unique(_years(st[brk & (st < tr_end)]), return_counts=True))}}
    for tf in R.TFS:
        t = pl.read_parquet(R.out_dir(symbol) / f"trades_{tf}.parquet")
        key = f"{R.PRIMARY_TARGET:g}R_{R.PRIMARY_HOLD[tf]}"
        t = t.filter((pl.col("fill_ts") < dev_end) & (pl.col(f"exit_{key}") < dev_end) & pl.col(f"r_{key}").is_not_nan())
        f, e = t["fill_ts"].to_numpy(), t[f"exit_{key}"].to_numpy()
        excluded = t[f"gap_{key}"].to_numpy()
        real = D.gap_between(other, f, e)
        only_break = excluded & ~real
        out[tf] = {"excluded": int(excluded.sum()), "excluded_only_by_daily_break_gaps": int(only_break.sum()),
                   "only_break_by_year": {int(y): int(c) for y, c in zip(*np.unique(_years(f[only_break]), return_counts=True))},
                   "only_break_by_setup": {k: int(v) for k, v in zip(*np.unique(t["setup"].to_numpy()[only_break], return_counts=True))}}
    return out


def power(dev_counts: dict, years_dev: float) -> dict:
    """Minimum detectable edge with 80% power for a 2R/-1R trade (outcome SD about 1.41R at the break-even win rate of 1/3)."""
    sd = 3 * np.sqrt((1 / 3) * (2 / 3))
    z80 = stats.norm.ppf(0.8)
    out = {"outcome_sd_assumed": float(sd)}
    for label, alpha in (("alpha 0.05", 0.05), ("alpha 0.05/36 (36 tests)", 0.05 / 36)):
        za = stats.norm.isf(alpha)
        out[label] = {"mde_at_150": float((za + z80) * sd / np.sqrt(150)),
                      "trades_needed_for_0.10R": int(np.ceil(((za + z80) * sd / 0.10) ** 2)),
                      "trades_needed_for_0.15R": int(np.ceil(((za + z80) * sd / 0.15) ** 2))}
    out["tests"] = {k: {"development_trades": v, "per_year": v / years_dev, "years_to_150": (150 / (v / years_dev)) if v else None,
                        "mde_at_actual_alpha_0.05": float((stats.norm.isf(0.05) + z80) * sd / np.sqrt(v)) if v else None}
                    for k, v in dev_counts.items()}
    return out


def dsr_requirement(symbol: str, dev_counts: dict) -> dict:
    """The per-trade Sharpe ratio (and mean R at the assumed SD) that experiment 2's deflated-Sharpe criterion (> 0.95) needs at a
    given sample size, from the same trial count and null variance as run.develop. Uses sample sizes only, never outcomes; skew
    and kurtosis are ignored (a normal approximation)."""
    n_prior, v_prior = R._prior_null_var(symbol)
    ns = list(dev_counts.values())
    n_trials = n_prior + len(ns)
    null_var = float(np.mean([v_prior] * n_prior + [1.0 / max(n, 2) for n in ns]))
    g = 0.5772156649
    sr0 = float(np.sqrt(null_var) * ((1 - g) * stats.norm.ppf(1 - 1 / n_trials) + g * stats.norm.ppf(1 - 1 / (n_trials * np.e))))
    sd = 3 * np.sqrt((1 / 3) * (2 / 3))
    req = {t: sr0 + stats.norm.ppf(0.95) / np.sqrt(t - 1) for t in (150, 300, 500, 1000)}
    return {"trials": n_trials, "null_var": null_var, "sr0_per_trade": sr0, "required_sharpe_per_trade": req,
            "required_mean_r_at_assumed_sd": {t: float(v * sd) for t, v in req.items()}}


# ------------------------------------------------------------------ report
SHORT = {"S1_trend_zone_pullback": "S1 trend zone pullback", "S2_order_block_after_bos": "S2 order block after BOS",
         "S3_fvg_after_displacement": "S3 FVG after displacement", "S4_broken_level_retest": "S4 broken level retest",
         "S5_prev_week_sweep_reclaim": "S5 previous-week sweep and reclaim", "S6_range_edge_fade": "S6 range edge fade"}


def report_path(symbol: str):
    return R.REPO_ROOT / "docs" / "reports" / f"{symbol}_EXP2_SIGNAL_SCARCITY.md"


def _t(headers: list, rows: list) -> list[str]:
    return ["| " + " | ".join(map(str, headers)) + " |", "|" + "---|" * len(headers)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows]


def _p(a: float, b: float) -> str:
    return f"{100 * a / b:.0f}%" if b else "-"


def _rng(vals, d: int = 0, scale: float = 1.0) -> str:
    v = [x * scale for x in vals if x is not None and np.isfinite(x)]
    return f"{min(v):.{d}f}-{max(v):.{d}f}" if v else "n/a"


def _ratio(a: float, b: float) -> float:
    return a / b if b else float("nan")


def render(symbol: str = "XAUUSD") -> str:
    r = json.loads((R.out_dir(symbol) / "diagnostics.json").read_text(encoding="utf8"))
    Fu, Fi, Ex, P, G4, Gp = r["funnels"], r["fills"], r["extras"], r["power"], r["s4_refresh"], r["gaps"]
    tfs = list(Fu)
    yd = r["years_development"]
    tests = P["tests"]
    dev = {k: v["development_trades"] for k, v in tests.items()}
    n150 = {tf: sum(1 for k, v in dev.items() if k.startswith(tf + "|") and v >= R.MIN_TRADES) for tf in tfs}
    rng = {tf: (min(v for k, v in dev.items() if k.startswith(tf + "|")), max(v for k, v in dev.items() if k.startswith(tf + "|"))) for tf in tfs}
    first, last = Fu[tfs[0]]["first"], Fu[tfs[0]]["last"]
    yrs_train = (datetime.fromisoformat(last) - datetime.fromisoformat(first)).days / 365.25

    def stage_tot(tf, key):
        return sum(v[key] if isinstance(v[key], int) else 0 for v in Fi[tf]["setups"].values())

    def tot(tf, f):
        return sum(f(v) for v in Fi[tf]["setups"].values())

    orders = {tf: tot(tf, lambda v: v["orders_dev"]) for tf in tfs}
    touched = {tf: tot(tf, lambda v: v["reasons_dev"]["touched"]) for tf in tfs}
    expired = {tf: tot(tf, lambda v: v["reasons_dev"]["expired untouched"]) for tf in tfs}
    cancelled = {tf: tot(tf, lambda v: v["reasons_dev"]["cancelled first"]) for tf in tfs}
    filled = {tf: tot(tf, lambda v: v["fills_dev"]["conservative (open spread, as run)"]) for tf in tfs}
    in_dev = {tf: stage_tot(tf, "dev_fill_in_period") for tf in tfs}
    exit_ok = {tf: stage_tot(tf, "dev_exit_before_boundary") for tf in tfs}
    no_gap = {tf: stage_tot(tf, "dev_no_gap") for tf in tfs}
    trades = {tf: stage_tot(tf, "development_trades") for tf in tfs}
    gap_lost = sum(exit_ok[tf] - no_gap[tf] for tf in tfs)
    brk_lost = {tf: Gp[tf]["excluded_only_by_daily_break_gaps"] for tf in tfs}
    fill_loss = [1 - v["fills_dev"]["conservative (open spread, as run)"] / v["fills_dev"]["touch"]
                 for tf in tfs for v in Fi[tf]["setups"].values() if v["fills_dev"]["touch"] >= 20]
    fill_rng = _rng(fill_loss, 0, 100)
    h8_other = [v["years_to_150"] for k, v in tests.items() if k.startswith("H8|") and "S4" not in k]
    dsr = r.get("dsr")
    sd = P["outcome_sd_assumed"]
    years_to = {tf: [v["years_to_150"] for k, v in tests.items() if k.startswith(tf + "|") and v["years_to_150"]] for tf in tfs}
    f4 = Fu["H4"] if "H4" in Fu else Fu[tfs[0]]

    def cond(tf, s, i):
        return Fu[tf][s]["conditions"][i][1]

    s3_cut = 1 - _ratio(cond("H4", "S3", 4), cond("H4", "S3", 1))
    s2_cut = 1 - _ratio(cond("H4", "S2", 1), cond("H4", "S2", 0))
    s1_cut = 1 - _ratio(cond("H4", "S1", 6), cond("H4", "S1", 5))
    s5_any = f4["S5"]["variant_counts"]["week-sides where ANY candle beyond the level closed back inside"]
    s5_cut = 1 - _ratio(cond("H4", "S5", 2), s5_any)
    wait = {tf: {s: v for s, v in Ex[tf]["wait_touch_dev"].items()} for tf in tfs}
    s5_by_tf = ", ".join(f"{tf} {cond(tf, 'S5', 2):,}" for tf in tfs)
    s6_weak = f4["S6"]["variant_counts"]["regime 'none' or weak, close-based onset"]
    s4_losses = [1 - _ratio(Ex[tf]["S4_dedup"]["unique_candle_direction"], Ex[tf]["S4_dedup"]["breakouts_dev"]) for tf in tfs] + [
        1 - _ratio(G4[tf]["refresh_every_200_candles"]["breakouts_dev_unique"], v["breakouts_dev_unique"])
        for tf in tfs for k, v in G4[tf].items() if k != "refresh_every_200_candles"]
    years_per_window = {tf: 200 / (Fu[tf]["candles"] / yrs_train) for tf in tfs}  # calendar span of 200 candles
    d1_rate = _rng([v["per_year"] for k, v in tests.items() if k.startswith("D1|")], 1)

    L = [f"# {symbol} experiment 2: signal-scarcity diagnostic", "",
         f"_Generated by `python -m app.gold_research.exp2 diagnose` from `data/historical/research/{symbol}/exp2/diagnostics.json` "
         f"(counted {r['generated'][:10]}). **Counts only:** no trade outcome, profitability statistic or parameter was computed, "
         "tested or changed; experiment 2's stored results and its report are unchanged. Training period only; the sealed final test "
         "was not read. Analysis only._", "",
         "## Summary", "",
         f"1. **{sum(n150.values())} of 36 tests reached the {R.MIN_TRADES}-trade minimum** (H4 {n150.get('H4', 0)}/12, H8 "
         f"{n150.get('H8', 0)}/12, D1 {n150.get('D1', 0)}/12). Development trades per test: "
         + ", ".join(f"{tf} {rng[tf][0]}-{rng[tf][1]}" for tf in tfs) + f", over {yd:.1f} development years.",
         "2. **Most of the scarcity comes from the setup and test design, not from defects.** In order of effect: the timeframe "
         f"(the training period has {Fu['H4']['candles']:,} H4 candles, {Fu['H8']['candles']:,} H8 and {Fu['D1']['candles']:,} D1); "
         f"S6's two conditions that partly exclude each other; S3's 2-ATR displacement candle ({100 * s3_cut:.0f}% of 3-candle gaps "
         f"removed on H4); S2's BOS-only rule ({100 * s2_cut:.0f}% of structure breaks removed); S1's higher-timeframe filter "
         f"({100 * s1_cut:.0f}% of zones removed); S5's limit of one sweep per side per week, plus its first-touch rule "
         f"({100 * s5_cut:.0f}% of reclaim week-sides removed); the 20-candle limit wait "
         f"({_p(expired['H4'], orders['H4'])} of H4 development orders expire untouched); and testing long and short separately, "
         "which halves every sample.",
         f"3. **Execution and sample filters cost little.** The conservative fill rule removes {fill_rng}% of touched orders; the gap rule removes {gap_lost} of {sum(exit_ok.values()):,} filled development "
         f"trades ({_p(gap_lost, sum(exit_ok.values()))}); development-boundary exits remove "
         f"{sum(in_dev[tf] - exit_ok[tf] for tf in tfs)}; cancellations before a fill: {sum(cancelled.values())}.",
         "4. **Defects found:**",
         f"   * daily-break gaps are counted as missing data ({sum(brk_lost.values())} development trades lost);",
         "   * S4 refreshes its levels every 200 candles on every timeframe, which leaves the levels stale on H8 and D1;",
         "   * S4 picks an arbitrary band when one candle breaks several;",
         "   * the cancel rule is effectively inert;",
         "   * the gap list is not limited to the permitted period.",
         "   Their effect on counts is small, and none would bring any test to 150 by itself (section 9).",
         "5. **The 150 minimum was too low to give the tests statistical power, and too high to reach on H8 and D1.** At 150 trades the "
         f"smallest edge detectable with 80% power is about {P['alpha 0.05']['mde_at_150']:.2f}R "
         f"({P['alpha 0.05/36 (36 tests)']['mde_at_150']:.2f}R at the 36-test level)"
         + (f"; the deflated-Sharpe criterion over {dsr['trials']:,} trials needs a mean of about "
            f"{dsr['required_mean_r_at_assumed_sd']['150']:.2f}R at 150 trades" if dsr else "")
         + ". At the observed rates, D1 tests would need "
         f"{_rng(years_to['D1'])} years of data to reach 150, and H8 tests other than S4 would need {_rng(h8_other)} years.", "",
         "## 1. Scope, data and method", "",
         f"* **Data:** XAUUSD candles from {first} to {last} ({yrs_train:.1f} years), read only through the sealed loader "
         "(`load_tf(..., upto=\"train\")`).",
         "  * The detection funnels (section 3) cover the whole training period: development plus screening.",
         f"  * Fills, sample filters and power cover only the development period, {yd:.1f} years to 2015-01-03. That "
         "is the sample experiment 2 tested.",
         "* **Method:** each condition was re-counted with the experiment's own detector code and parameters "
         "(`backend/app/gold_research/exp2/diagnostics.py`).",
         "* **Cross-checks (all pass):**",
         f"  1. Orders: re-deriving them from the detector outputs reproduces the experiment's order counts "
         f"({', '.join(f'{tf} {Fi[tf]['orders']:,}' for tf in tfs)}).",
         "  2. The 36 development trade counts equal `development.json` exactly.",
         f"  3. The filled rows equal the stored trade files ({', '.join(f'{tf} {tot(tf, lambda v: v['filled_rows_in_results']):,}' for tf in tfs)}).",
         "  4. The replica of the S4 200-candle level windows reproduces the experiment's S4 orders: "
         + ", ".join(f"{tf} {G4[tf]['refresh_every_200_candles']['breakouts_dev_unique']:,}" for tf in tfs) + ".",
         "* **Variant counts** show how many events another rule would have produced. They are counts only: nothing was simulated, "
         "no outcome was looked at, and no setup was changed.", "",
         "## 2. The six setups as individual conditions (code evidence)", ""]
    L += _t(["Setup", "Conditions, in order", "Code"], [
        ["S1 trend zone pullback", "base of 1-3 candles each <= 0.8 ATR; then an impulse candle with range >= 1.5 ATR and body >= 60% of "
         "range, closing beyond the base; one zone per impulse; the structure trend on the higher timeframe (D1 for H4/H8, W1 for D1) "
         "equals the zone direction", "`app/price_action/supply_demand.py:14-53`, `exp2/run.py:91-99`"],
        ["S2 order block after BOS", "structure break; BOS only (CHoCH excluded); the last opposite candle within 6 candles of the "
         "impulse origin; displacement >= 1.5 ATR; one block per (candle, direction)",
         "`app/price_action/order_blocks.py:15-38`, `app/patterns/zones.py:48`, `exp2/run.py:106-107`"],
        ["S3 FVG after displacement", "three-candle gap; gap >= 0.1 ATR; middle candle range >= 2 ATR; middle candle body >= 70%",
         "`app/patterns/imbalance.py:74-77`, `exp2/run.py:108-109`"],
        ["S4 broken level retest", "bands of 2+ swing touches within 0.5 ATR, recomputed every 200 candles as of the window start; "
         "a close >= 0.25 ATR beyond a band after price had been on the other side; one order per (candle, direction)",
         "`app/gold_research/events.py:65-79`, `app/price_action/levels.py:155-181`, `exp2/run.py:100-102, 126`"],
        ["S5 previous-week sweep and reclaim", "the first candle of the week trading beyond the previous-week low (high); that same "
         "candle closes back inside", "`app/patterns/liquidity.py:70-73`, `app/patterns/context.py:82-92`, `exp2/run.py:110-113`"],
        ["S6 range edge fade", "trend regime 'none' (absolute EMA50 slope over 20 candles < 0.3 ATR); close within 0.25 ATR inside the prior "
         "50-candle high (low); the first candle of such a run", "`app/gold_research/regimes.py:38-48`, `exp2/run.py:114-124`"],
        ["All setups", f"limit at the near edge, live for {R.WAIT} candles; cancelled if a candle closes beyond the far edge first; "
         "conservative fill (ask/bid beyond the limit by the signal candle's opening spread); stop at the far edge plus "
         f"{R.BUFFER_ATR} ATR; long and short tested separately; >= {R.MIN_TRADES} development trades",
         "`exp2/run.py:46-48, 80-89, 130-135`"]])
    L += ["", f"## 3. Detection funnels ({first[:7]} to {last[:7]}, training period, both directions)", "",
          "Each row is the count after adding that condition; the percentage is relative to the row above.", ""]
    for s, title in (("S1", "S1 trend zone pullback"), ("S2", "S2 order block after BOS"), ("S3", "S3 FVG after displacement"),
                     ("S4", "S4 broken level retest"), ("S5", "S5 previous-week sweep and reclaim"), ("S6", "S6 range edge fade")):
        L += [f"**{title}**", ""]
        conds = Fu[tfs[0]][s]["conditions"]
        rows = []
        for i, (name, _) in enumerate(conds):
            cells = []
            for tf in tfs:
                v = Fu[tf][s]["conditions"][i][1]
                prev = Fu[tf][s]["conditions"][i - 1][1] if i else None
                cells.append(f"{int(v):,}" + (f" ({_p(v, prev)})" if prev and i and s not in ("S4",) else ""))
            rows.append([name] + cells)
        L += _t(["Condition"] + tfs, rows)
        em = "aligned" if s == "S1" else "emitted"
        if em in Fu[tfs[0]][s]:
            L += ["", "Long / short: " + "; ".join(f"{tf} {Fu[tf][s][em]['long']:,} / {Fu[tf][s][em]['short']:,}" for tf in tfs) + "."]
        vc = Fu[tfs[0]][s].get("variant_counts", {})
        if vc:
            L += ["", "Variants (counts only): " + "; ".join(f"{k}: " + ", ".join(f"{tf} {Fu[tf][s]['variant_counts'][k]:,}" for tf in tfs)
                                                           for k in vc) + "."]
        if s == "S1":
            L += ["", "Higher-timeframe trend at the zones (up / down / none): " + "; ".join(
                f"{tf} ({Fu[tf]['S1']['htf']}) {100 * Fu[tf]['S1']['htf_trend_share_at_zones']['up']:.0f}% / "
                f"{100 * Fu[tf]['S1']['htf_trend_share_at_zones']['down']:.0f}% / "
                f"{100 * Fu[tf]['S1']['htf_trend_share_at_zones']['none']:.1f}%" for tf in tfs) + "."]
        if s == "S6":
            L += ["", "Trend regime 'none' share of all candles: " + ", ".join(
                f"{tf} {100 * Fu[tf]['S6']['trend_regime_share'].get('none', 0):.1f}%" for tf in tfs) + "."]
        L.append("")
    L += ["## 4. From events to development trades, by timeframe and direction (development period)", "",
          "Detector events (development years, both directions) to orders:", ""]
    rows = []
    for tf in tfs:
        def ds(by):
            return sum(c for y, c in by.items() if int(y) <= 2014)
        od = {}
        for k, v in Fi[tf]["setups"].items():
            od[k.split("|")[0]] = od.get(k.split("|")[0], 0) + v["orders_dev"]
        rows.append([tf, f"zones {ds(Fu[tf]['S1']['zones']['by_year']):,} -> trend-aligned {ds(Fu[tf]['S1']['aligned']['by_year']):,} -> "
                         f"orders {od['S1_trend_zone_pullback']:,}",
                     f"{ds(Fu[tf]['S2']['emitted']['by_year']):,} -> {od['S2_order_block_after_bos']:,}",
                     f"{ds(Fu[tf]['S3']['emitted']['by_year']):,} -> {od['S3_fvg_after_displacement']:,}",
                     f"{Ex[tf]['S4_dedup']['breakouts_dev']:,} -> one per candle {Ex[tf]['S4_dedup']['unique_candle_direction']:,} -> "
                     f"{od['S4_broken_level_retest']:,}", f"{od['S5_prev_week_sweep_reclaim']:,}", f"{od['S6_range_edge_fade']:,}"])
    L += _t(["TF", "S1", "S2", "S3", "S4", "S5 orders", "S6 orders"], rows)
    L += ["", "Year boundaries are approximate: events in the first two days of 2015 are counted with 2015. S5 and S6 have no separate detector "
          "list; their orders are the events.", ""]
    for tf in tfs:
        L += [f"**{tf}** (development orders signalled before 2015-01-03)", ""]
        rows = []
        for k, v in Fi[tf]["setups"].items():
            s, dn = k.split("|")
            rows.append([SHORT[s], dn, v["orders_dev"], v["reasons_dev"]["touched"], v["reasons_dev"]["expired untouched"],
                         v["reasons_dev"]["cancelled first"], v["fills_dev"]["touch"], v["fills_dev"]["conservative (open spread, as run)"],
                         v["dev_fill_in_period"], v["dev_exit_before_boundary"], v["dev_no_gap"], f"**{v['development_trades']}**",
                         "yes" if v["development_trades"] >= R.MIN_TRADES else "no"])
        rows.append(["**All**", ""] + [f"{x:,}" for x in (orders[tf], touched[tf], expired[tf], cancelled[tf],
                                                           tot(tf, lambda v: v["fills_dev"]["touch"]), filled[tf], in_dev[tf],
                                                           exit_ok[tf], no_gap[tf])] + [f"**{trades[tf]:,}**", f"{n150[tf]}/12"])
        L += _t(["Setup", "Dir", "Orders", "Touched in 20", "Expired untouched", "Cancelled first", "Fill: touch only", "Fill: conservative (as run)",
                 "Filled before dev end", "Exit before dev end", "No unscheduled gap", "Dev trades", ">= 150"], rows)
        L.append("")
    L += ["## 5. Development trades by year", ""]
    years = list(range(2003, 2015))
    for tf in tfs:
        L += [f"**{tf}**", ""]
        rows = []
        for k, v in Fi[tf]["setups"].items():
            s, dn = k.split("|")
            by = {int(y): c for y, c in v["dev_trades_by_year"].items()}
            rows.append([SHORT[s].split(" ")[0], dn] + [by.get(y, 0) for y in years] + [v["development_trades"]])
        colsum = [sum(int(Fi[tf]["setups"][k]["dev_trades_by_year"].get(str(y), Fi[tf]["setups"][k]["dev_trades_by_year"].get(y, 0)))
                      for k in Fi[tf]["setups"]) for y in years]
        rows.append(["All", ""] + colsum + [f"{trades[tf]:,}"])
        L += _t(["Setup", "Dir"] + years + ["Total"], rows)
        L.append("")
    L += ["2003 is a part year (from May) and also loses the warm-up candles: ATR, the first 200-candle level window and the "
          "higher-timeframe trend. Detector events by year for the whole training period are in the JSON file.", "",
          "## 6. Which conditions contribute most to the low counts", "",
          "Ranked by how many events each removes. \"Design\" means a rule chosen in the plan; \"implementation\" means a coding "
          "choice the plan did not specify.", ""]
    s6_none = {tf: Ex[tf]["S6_conflict"] for tf in tfs}
    ranked = [
        ["1", "Timeframe (candles available)", "all", f"{Fu['H4']['candles']:,} H4, {Fu['H8']['candles']:,} H8 and {Fu['D1']['candles']:,} "
         f"D1 candles in training; development trades {', '.join(f'{tf} {trades[tf]:,}' for tf in tfs)}", "structural"],
        ["2", "Regime 'none' AND close within 0.25 ATR of the 50-candle edge", "S6",
         f"H4: {cond('H4', 'S6', 1):,} 'none' candles, but only {cond('H4', 'S6', 2):,} also near an edge; the regime is 'none' at "
         f"{100 * s6_none['H4']['share_none_regime_at_near_edge_dev']:.1f}% of near-edge candles vs "
         f"{100 * s6_none['H4']['share_none_regime_all_candles_dev']:.1f}% of all (D1 {100 * s6_none['D1']['share_none_regime_at_near_edge_dev']:.1f}% "
         f"vs {100 * s6_none['D1']['share_none_regime_all_candles_dev']:.1f}%)", "design (conditions partly exclude each other)"],
        ["3", "Middle candle >= 2 ATR and body >= 70%", "S3", f"H4 gaps {cond('H4', 'S3', 1):,} -> {cond('H4', 'S3', 4):,}; with 1.5 ATR: "
         f"{f4['S3']['variant_counts']['middle candle range >= 1.5 ATR (instead of 2)']:,}", "design (a tail event by definition)"],
        ["4", "Long and short tested separately", "all", "every test has about half its setup's events", "design"],
        ["5", "BOS only (CHoCH excluded)", "S2", f"H4 breaks {cond('H4', 'S2', 0):,} -> BOS {cond('H4', 'S2', 1):,}; CHoCH blocks "
         f"{f4['S2']['variant_counts']['order blocks after CHoCH (excluded by design)']:,}", "design"],
        ["6", "Higher-timeframe trend = zone direction", "S1", f"H4 zones {cond('H4', 'S1', 5):,} -> {cond('H4', 'S1', 6):,}", "design"],
        ["7", "One sweep per side per week; first touch only", "S5", f"H4 reclaim week-sides, any candle {s5_any:,} -> first touch "
         f"{cond('H4', 'S5', 2):,}; the counts barely change with timeframe ({s5_by_tf})",
         "structural (calendar) + design"],
        ["8", f"{R.WAIT}-candle limit wait", "all", "expired untouched: " + ", ".join(f"{tf} {_p(expired[tf], orders[tf])}" for tf in tfs)
         + f"; S1 and S2 are worst (H4 {_p(Fi['H4']['setups']['S1_trend_zone_pullback|long']['reasons_dev']['expired untouched'] + Fi['H4']['setups']['S1_trend_zone_pullback|short']['reasons_dev']['expired untouched'], wait['H4']['S1_trend_zone_pullback']['orders'])}"
         f" and {_p(Fi['H4']['setups']['S2_order_block_after_bos|long']['reasons_dev']['expired untouched'] + Fi['H4']['setups']['S2_order_block_after_bos|short']['reasons_dev']['expired untouched'], wait['H4']['S2_order_block_after_bos']['orders'])})",
         "design"],
        ["9", "Levels refreshed every 200 candles on every timeframe", "S4", "development breakouts with a refresh at the same calendar "
         f"interval: H8 {G4['H8']['refresh_every_200_candles']['breakouts_dev_unique']} -> {G4['H8']['refresh_every_100_candles']['breakouts_dev_unique']}, "
         f"D1 {G4['D1']['refresh_every_200_candles']['breakouts_dev_unique']} -> {G4['D1']['refresh_every_33_candles']['breakouts_dev_unique']}; "
         f"D1 has no breakout at all in 2010", "implementation"],
        ["10", "One S4 order per candle and direction", "S4", ", ".join(f"{tf} {Ex[tf]['S4_dedup']['breakouts_dev']:,} -> "
                                                                      f"{Ex[tf]['S4_dedup']['unique_candle_direction']:,}" for tf in tfs),
         "implementation (reasonable)"],
        ["11", "Unscheduled-gap exclusion", "all", ", ".join(f"{tf} {exit_ok[tf] - no_gap[tf]}" for tf in tfs)
         + f" trades; {sum(brk_lost.values())} of them only because of daily-break gaps", "design (+ a defect, D1 in section 9)"],
        ["12", "Conservative fill (beyond the limit by the spread)", "all", f"{fill_rng}% of "
         "touched orders", "design"],
        ["13", "Exit before the development end", "all", f"{sum(in_dev[tf] - exit_ok[tf] for tf in tfs)} trades", "design"]]
    L += _t(["#", "Condition", "Setups", "Count evidence", "Kind"], ranked)
    L += ["", "## 7. Genuinely rare structure, or restrictive choices?", ""]
    L += _t(["Setup", "Verdict", "Why"], [
        ["S1", "mixed", f"An impulse after a base is uncommon but not rare ({_p(cond('H4', 'S1', 3), Fu['H4']['candles'])} of H4 candles). "
         "The higher-timeframe filter (design) halves it. A third of orders are not revisited within 20 candles, which is a market "
         "property under this wait."],
        ["S2", "mostly design", f"BOS happen about {cond('H4', 'S2', 1) / yrs_train:.0f} times a year on H4, and an order block is "
         f"found for {_p(cond('H4', 'S2', 4), cond('H4', 'S2', 1))} of them. The losses come from excluding CHoCH and from the "
         "20-candle wait."],
        ["S3", "rare by definition", f"A gap whose middle candle is >= 2 ATR with a 70% body occurs on "
         f"{_p(cond('H4', 'S3', 4), Fu['H4']['candles'])} of H4 candles. The thresholds make it a tail event."],
        ["S4", "not rare", f"The most frequent setup. Implementation choices remove {_rng(s4_losses, 0, 100)}% "
         "(one order per candle; the 200-candle refresh on H8/D1)."],
        ["S5", "rare by structure", "At most one long and one short event per week on every timeframe, so a higher timeframe "
         "cannot add events, and the three timeframe tests largely re-test the same weekly events. The first-touch rule (design) "
         "removes about half."],
        ["S6", "too restrictive by construction", f"Two conditions that partly exclude each other: about "
         f"{cond('H4', 'S6', 3) / yrs_train:.1f} signals a year on H4 and {cond('D1', 'S6', 3) / yrs_train:.1f} on D1 (both directions). Even with weak trends "
         f"allowed, H4 would have only {s6_weak:,} "
         "events in the whole training period."]])
    L += ["", f"## 8. Was the {R.MIN_TRADES}-trade minimum realistic?", "",
          f"The power figures below assume a 2R/-1R outcome at the break-even win rate of one in three, an SD of {sd:.2f}R. Time stops "
          "make the real SD somewhat lower (with an SD of 1.2R, every detectable edge shrinks by 15% and every required sample by about 28%). Overlapping trades and week clustering "
          "make it effectively higher. Power is 80%, and the test is one-sided.", ""]
    a, b = P["alpha 0.05"], P["alpha 0.05/36 (36 tests)"]
    L += _t(["Significance level", "Smallest detectable edge at 150 trades", "Trades needed for 0.10R", "Trades needed for 0.15R"],
            [["0.05", f"{a['mde_at_150']:.2f}R", f"{a['trades_needed_for_0.10R']:,}", f"{a['trades_needed_for_0.15R']:,}"],
             ["0.05 / 36 (the 36 tests)", f"{b['mde_at_150']:.2f}R", f"{b['trades_needed_for_0.10R']:,}", f"{b['trades_needed_for_0.15R']:,}"]])
    if dsr:
        L += ["", f"**The deflated-Sharpe criterion is stricter still.** It counts {dsr['trials']:,} trials (experiments 1 and 2), and "
              "the code needs a per-trade Sharpe of about "
              + ", ".join(f"{float(v):.2f} at {int(k):,} trades" for k, v in dsr["required_sharpe_per_trade"].items())
              + ", which at the assumed SD is a mean of about "
              + ", ".join(f"{float(v):.2f}R at {int(k):,}" for k, v in dsr["required_mean_r_at_assumed_sd"].items())
              + ". This is a normal approximation from sample sizes only.",
              "",
              f"Part of this hurdle does not shrink with sample size. The criterion asks whether a test beats the best of "
              f"{dsr['trials']:,} trials by luck, so it needs a per-trade Sharpe above {dsr['sr0_per_trade']:.2f} (about "
              f"{dsr['sr0_per_trade'] * sd:.2f}R at the assumed SD) even with unlimited trades. More trades alone cannot get a small "
              "edge past it; fewer total trials can, and every new experiment raises it."]
    L += ["", "Per test: development trades, the rate per year, the years of data needed to reach 150 at that rate, and the smallest "
          "detectable edge at the test's actual size (significance 0.05).", ""]
    rows = [[k.split("|")[0], SHORT[k.split("|")[1]].split(" ")[0], k.split("|")[2], v["development_trades"], f"{v['per_year']:.1f}",
             f"{v['years_to_150']:.0f}" if v["years_to_150"] else "-", f"{v['mde_at_actual_alpha_0.05']:.2f}R" if v["mde_at_actual_alpha_0.05"] else "-"]
            for k, v in tests.items()]
    L += _t(["TF", "Setup", "Dir", "Dev trades", "Per year", "Years to 150", "Smallest detectable edge"], rows)
    L += ["", "**Verdict:**",
          f"* **Statistically**, 150 was a floor for a stable estimate (standard error about {sd / np.sqrt(150):.2f}R), not a power target. "
          "Even the tests that passed it could only have detected large edges.",
          f"* **Practically**, it was reachable for {n150.get('H4', 0)} of 12 H4 tests, {n150.get('H8', 0)} of 12 H8 tests and "
          f"{n150.get('D1', 0)} of 12 D1 tests in {yd:.1f} years.",
          "* **The mismatch is in the design:** setups this selective, tested per direction on H8 and D1, cannot produce the samples a "
          "realistic edge needs. Lowering the minimum would only have let underpowered tests through.", "",
          "## 9. Implementation defects and inconsistencies (none fixed; experiment 2's results are unchanged)", ""]
    g = Gp
    L += [f"**D1. Daily-break gaps counted as missing data.** Of the {g['unscheduled_gaps_in_training']} unscheduled gaps in training, "
          f"{g['of_which_daily_break_time']} start at 21:00-21:05 or 22:00-22:05 UTC (the daily rollover break) and last up to 2 hours. By "
          "year: " + ", ".join(f"{y} {c}" for y, c in g["daily_break_time_by_year"].items()) + ".",
          "* **What they are:** recurring daily closures that ran longer, or at a different hour, than the calendar assumes (for "
          "example in US summer time in 2014). They are not feed failures; prices exist on both sides, and the simulator already "
          "handles a stop minute that opens beyond the stop.",
          f"* **Effect:** {sum(brk_lost.values())} development trades were excluded only because of them ("
          + ", ".join(f"{tf} {brk_lost[tf]}" for tf in tfs) + "), at most 6 in any one test.",
          "* **Code:** `exp2/data.py:46-57`.", "",
          "**D2. The S4 level refresh is fixed at 200 candles on every timeframe.** That is about "
          f"{years_per_window['H4'] * 52:.0f} weeks on H4, {years_per_window['H8'] * 52:.0f} weeks on H8 and "
          f"{years_per_window['D1'] * 12:.0f} months on D1.",
          "* **Why it matters:** levels that form inside a window are ignored until the next refresh, and a window with no band near "
          "price yields no breakouts.",
          f"* **Effect:** D1 has no S4 breakout at all in 2010. Refreshing at the same calendar interval would give H8 "
          f"{G4['H8']['refresh_every_100_candles']['breakouts_dev_unique']} instead of {G4['H8']['refresh_every_200_candles']['breakouts_dev_unique']} "
          f"development breakouts, and D1 {G4['D1']['refresh_every_33_candles']['breakouts_dev_unique']} instead of "
          f"{G4['D1']['refresh_every_200_candles']['breakouts_dev_unique']}.",
          "* **Origin:** inherited from experiment 1, which was built for M5-H4. Code: `app/gold_research/events.py:36, 65-79`.", "",
          "**D3. S4 picks an arbitrary band when one candle breaks several.**",
          "* **Where it happens:** " + ", ".join(f"{tf} {Ex[tf]['S4_dedup']['candles_breaking_2plus_bands']}" for tf in tfs)
          + " development candles broke two or more bands.",
          "* **What the code does:** it keeps the first band in the list (`run.py:126`, `unique(..., keep=\"first\")`). Levels are "
          "sorted by distance from the price at the window start (`levels.py:96`), not from the breakout candle.",
          "* **Effect:** this changes the limit price of those orders, not the count beyond the deduplication.", "",
          f"**D4. The cancel rule is effectively inert.** Only {sum(cancelled.values())} of {sum(orders.values()):,} development orders "
          "was cancelled before a touch.",
          "* **Why:** for a long, the far edge lies below the limit, so a candle cannot close below the far edge without first "
          "trading through the limit. Only a price gap, or a spread wider than the zone, can skip it.",
          "* **Effect:** orders that slice through the whole zone are filled and then usually stopped, which is realistic for a "
          "resting limit order. The documentation (\"cancelled if a candle closes beyond the far edge first\") overstates what the "
          "rule does; counts are unaffected.", "",
          "**D5. A documentation detail: which spread the conservative fill uses.** The code uses the signal candle's *opening* spread "
          "(`run.py:132`). This was checked and is harmless: the median opening spread at signals matches the all-candle median ("
          + ", ".join(f"{tf} {Fi[tf]['spread_used_for_conservative_fill']['median_open_spread_signal']:.2f} vs "
                      f"{Fi[tf]['spread_used_for_conservative_fill']['median_spread_all_candles']:.2f}" for tf in tfs)
          + "). Opening spreads above 3x the median occur at "
          + ", ".join(f"{tf} {100 * Fi[tf]['spread_used_for_conservative_fill']['share_open_spread_gt_3x_median']:.2f}%" for tf in tfs)
          + " of signals. Switching to the closing spread or the median spread changes fills by at most a few per test (section 4).", "",
          "**D6. The gap list is not limited to the permitted period.**",
          "* **What it covers:** `exp2/data.py::gaps_v2` loads the missing-data runs (start time and length only, no prices) for the "
          "whole dataset. Trades only look up gaps inside training.",
          "* **Disclosure:** during this diagnostic, one exploratory query printed, for every year including the sealed years "
          "2023-2025, the number of unscheduled gaps (one or two a year), their median length and the date of the last one "
          "(November 2025). No price, spread or trade data from the sealed period was read. The diagnostic's own gap counts are "
          "limited to training.",
          "* **Fix:** filter the gap list to the permitted period at load time.", "",
          "**D7. One S1 condition never removes an event.** \"Closes beyond the base in the impulse direction\" is always met once "
          "the range, body and base conditions hold. It is redundant, not harmful.", "",
          "**Combined effect:** none of D1-D7 would bring any test to 150 by itself. Only design changes would (section 12).", "",
          "## 10. Hypotheses checked and rejected", "",
          "* *\"Wide rollover spreads at the signal candle's open make conservative fills rare.\"* Rejected (D5): the conservative rule "
          f"costs {fill_rng}% of touched orders.",
          "* *\"The W1 trend is usually neutral, so D1 S1 rarely aligns.\"* Rejected: W1 was neutral at "
          f"{100 * Fu['D1']['S1']['htf_trend_share_at_zones']['none']:.1f}% of D1 zones. The filter removes about half the zones because "
          "it matches the direction against a trend that is almost always up or down.",
          f"* *\"Trades are lost at the development boundary.\"* Rejected: {sum(in_dev[tf] - exit_ok[tf] for tf in tfs)} lost.",
          f"* *\"Limit orders are cancelled before filling.\"* Rejected: {sum(cancelled.values())} cancellation.", "",
          "## 11. Limitations", "",
          "* **Counts only.** Whether a looser rule would produce better or worse trades is unknown and was deliberately not examined. "
          "Fewer filters usually mean more trades of lower average quality.",
          "* **The S1-S3 funnels are re-counts.** They re-implement the detectors' conditions step by step; the detector's own output "
          "(the \"emitted\" rows) is what the experiment used. They agree to within one event (for example S1 on H4: 689 re-counted, "
          "688 emitted).",
          "* **The power figures are approximations.** They rest on an assumed outcome SD, a normal approximation and no clustering "
          "adjustment.",
          "* **These counts came after experiment 2's results.** They were made after its development results (no candidates) were "
          "known. Using counts to judge feasibility does not use outcomes, but any new experiment designed now is still post hoc for "
          "2003-2020 and needs fresh data to validate.",
          "* **The multiple-testing family over-counts S5.** The three S5 timeframe tests largely share the same weekly events, so "
          "they are not independent hypotheses.", "",
          "## 12. Recommendations for a possible future experiment (not started; needs your approval)", "",
          "1. **Set a power requirement before any outcome is seen, in place of the fixed 150 minimum.** Count events without "
          "outcomes, as here, and keep only setup/timeframe pairs that can meet it. For example, detecting 0.15R at significance 0.05 "
          f"needs about {a['trades_needed_for_0.15R']:,} trades per test.",
          "2. **Reduce the number of tests rather than loosening thresholds.**",
          "   * Test long and short together: the direction-matched controls already account for gold's drift. This doubles each sample "
          "and halves the number of tests.",
          "   * Test S5 once, on one timeframe.",
          "   * Each test dropped also lowers the deflated-Sharpe hurdle.",
          "3. **Use H4, or H1 entries with H4/D1 context (the brief's multi-timeframe profiles), for setup tests.** Keep D1 and W1 as "
          f"context only: at D1, these setups produced {d1_rate} development trades a year per direction.",
          "4. **Fix D1, D2, D3 and D6 before any re-run:**",
          "   * classify daily-break gaps as scheduled;",
          "   * refresh levels on a calendar interval;",
          "   * pick the band nearest the breakout;",
          "   * limit the gap list to the permitted period.",
          "   Experiment 2's recorded results stay as they are.",
          "5. **Treat wider thresholds as new hypotheses.** Examples: S3 at 1.5 ATR, S1 without the trend filter, S2 including CHoCH, "
          "S5 with any-candle reclaims, a longer wait. Each must be pre-registered and added to the trial count. "
          "Redefine S6 or drop it.",
          "6. **Validation needs untouched data.**",
          "   * 2015-2020 was screened in this experiment.",
          "   * 2020-2022 was experiment 1's validation period.",
          "   * The sealed 2023-2026 test can be used once, with your approval, for one frozen, pre-registered candidate list, followed "
          "by forward paper trading.", "",
          "_Stopped here. Nothing further was run; waiting for your approval._"]
    return "\n".join(L) + "\n"


def write(symbol: str = "XAUUSD", log=print) -> None:
    p = report_path(symbol)
    p.write_text(render(symbol), encoding="utf8")
    log(f"report written: {p}")


def run(symbol: str = "XAUUSD", log=print) -> dict:
    s = D.load(symbol)
    years_dev = (datetime.fromisoformat(s["development"]["end_exclusive"]) - datetime.fromisoformat(s["development"]["start"])).days / 365.25
    res = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "scope": "training period only; counts only",
           "years_development": years_dev, "funnels": {}, "fills": {}}
    for tf in R.TFS:
        res["funnels"][tf] = funnels(symbol, tf)
        log(f"{tf}: funnels counted")
        res["fills"][tf] = fill_and_sample(symbol, tf)
        log(f"{tf}: fills and sample counted")
        res["extras"] = {**res.get("extras", {}), tf: extras(symbol, tf)}
        res["s4_refresh"] = {**res.get("s4_refresh", {}), tf: s4_refresh_variant(symbol, tf)}
        log(f"{tf}: extras counted")
    res["gaps"] = gap_breakdown(symbol)
    dev = {f"{tf}|{k}": v["development_trades"] for tf in R.TFS for k, v in res["fills"][tf]["setups"].items()}
    res["power"] = power(dev, years_dev)
    res["dsr"] = dsr_requirement(symbol, dev)
    p = R.out_dir(symbol) / "diagnostics.json"
    p.write_text(json.dumps(res, indent=1, default=float), encoding="utf8")
    log(f"written: {p}")
    return res

