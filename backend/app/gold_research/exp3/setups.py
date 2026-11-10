"""Experiment-3 setups, pre-registered in docs/research/EXPERIMENT_3_PLAN.md section 5. Analysis only.

Every order is (direction, signal candle, limit, far edge): the limit is placed at the signal close at a level known then; the far
edge is the cancel level and, with 0.1 ATR added, the stop. Long and short are pooled per setup and timeframe in the tests, but every
trade keeps its own direction for the direction-matched controls.

Fixes (each tested): F2 support/resistance levels are refreshed at the start of every trading week (every 5 trading days, on every
timeframe) from swings confirmed before it; F3 when one candle breaks several bands the band whose broken edge is nearest the
breakout close is used; F5 order blocks after BOS or CHoCH, displacement at 1.5 ATR, previous-day sweep reclaimed by any candle of
the same day.
"""
import numpy as np
import polars as pl

from app.market_data.bars import Bars
from app.market_structure.bos import detect_structure_breaks
from app.market_structure.swings import find_swings
from app.price_action.fvg import detect_fvg
from app.price_action.levels import BreakoutParams, detect_breakouts, detect_levels
from app.price_action.order_blocks import detect_order_blocks
from app.price_action.supply_demand import detect_supply_demand

TFS = ("H1", "H4")
SETUPS = {
    "E1_order_block_after_break": "order block whose impulse broke structure (BOS or CHoCH), displacement >= 1.5 ATR",
    "E2_fvg_displacement_1p5": "fair value gap whose middle candle has range >= 1.5 ATR and a body >= 70% of its range",
    "E3_broken_level_retest": "support/resistance band (levels refreshed weekly) broken by a close >= 0.25 ATR beyond it; limit at the broken edge",
    "E4_zone_pullback_d1_trend": "demand (supply) zone with the D1 structure trend in the trade's direction",
    "E5_prev_day_sweep_reclaim": "price trades beyond the previous New York day's low (high) and a candle of the same day closes back inside",
}
TESTS = [(s, tf) for s in SETUPS for tf in TFS if not (s.startswith("E5") and tf != "H1")]  # 9 pre-registered tests
DISPLACEMENT_ATR, DISPLACEMENT_BODY = 1.5, 0.7
MIN_HISTORY = 50  # candles before the first weekly level refresh


def nearest_band(events: list, close: np.ndarray) -> list:
    """F3: one breakout per (candle, direction), the band whose broken edge is nearest the breakout close."""
    best: dict = {}
    for e in events:
        edge = e.high if e.direction == "bullish" else e.low
        dist = abs(float(close[e.idx]) - edge)
        key = (e.idx, e.direction)
        if key not in best or dist < best[key][0]:
            best[key] = (dist, e)
    return [v[1] for v in sorted(best.values(), key=lambda x: (x[1].idx, x[1].direction))]


def weekly_breakouts(b: Bars, swings, atr: np.ndarray, week_id: np.ndarray, tail: int = 20) -> list:
    """F2: levels as of the last candle before each trading week; breakouts whose candle falls inside that week."""
    n = len(b)
    starts = np.flatnonzero(np.r_[True, week_id[1:] != week_id[:-1]])
    out = []
    for k, w in enumerate(starts):
        if w < MIN_HISTORY:
            continue
        end = int(starts[k + 1]) if k + 1 < len(starts) else n
        levels = detect_levels(b, swings, atr, as_of=int(w) - 1)
        if not levels:
            continue
        sub = b.upto(min(n, end + tail))
        for e in detect_breakouts(sub, levels, atr[:len(sub)], BreakoutParams(lookback_bars=len(sub) - int(w))):
            if e.kind == "breakout" and w <= e.idx < end:
                out.append(e)
    return nearest_band(out, b.c)


def prev_day_sweep_reclaim(h: np.ndarray, lo: np.ndarray, c: np.ndarray, pdh: np.ndarray, pdl: np.ndarray,
                           day_id: np.ndarray) -> list[tuple[int, int, float, float]]:
    """F5: per New York day and side, the first candle that closes back inside after price traded beyond the previous day's low
    (high), in the same day. Returns (direction, signal index, limit, far): limit = the level, far = the sweep extreme so far."""
    out = []
    n = len(c)
    starts = np.flatnonzero(np.r_[True, day_id[1:] != day_id[:-1]])
    bounds = np.r_[starts, n]
    for a, e in zip(bounds[:-1], bounds[1:]):
        for side in (1, -1):
            lvl = pdl[a] if side > 0 else pdh[a]
            if not np.isfinite(lvl):
                continue
            beyond = (lo[a:e] < lvl) if side > 0 else (h[a:e] > lvl)
            if not beyond.any():
                continue
            j = a + int(np.argmax(beyond))
            back = (c[j:e] > lvl) if side > 0 else (c[j:e] < lvl)
            if not back.any():
                continue
            k = j + int(np.argmax(back))
            far = float(lo[j:k + 1].min()) if side > 0 else float(h[j:k + 1].max())
            out.append((side, k, float(lvl), far))
    return out


def setup_orders(b: Bars, atr: np.ndarray, levels, htf_trend: np.ndarray, tf: str) -> pl.DataFrame:
    """All orders of the setups tested on `tf`. `levels` from app.patterns.context.compute_levels; `htf_trend` = D1 structure
    trend known at each candle's close (+1 / -1 / 0)."""
    o, h, lo, c = b.o, b.h, b.l, b.c
    rows: dict[str, list] = {k: [] for k in ("setup", "direction", "idx", "limit", "far")}

    def put(setup, d, i, limit, far):
        if not (np.isfinite(limit) and np.isfinite(far)) or i + 1 >= len(b) or not np.isfinite(atr[i]):
            return
        if (d > 0 and not (far < limit <= c[i])) or (d < 0 and not (far > limit >= c[i])):
            return  # the limit must be at or beyond the signal close on the entry side, and the far edge beyond the limit
        rows["setup"].append(setup)
        rows["direction"].append(d)
        rows["idx"].append(int(i))
        rows["limit"].append(float(limit))
        rows["far"].append(float(far))

    swings = find_swings(b)
    breaks, _trend = detect_structure_breaks(b, swings)
    for ob in detect_order_blocks(b, breaks, atr):  # BOS and CHoCH, displacement >= 1.5 ATR (detector default)
        d = 1 if ob.direction == "bullish" else -1
        put("E1_order_block_after_break", d, ob.idx, ob.high if d > 0 else ob.low, ob.low if d > 0 else ob.high)
    rng, body = h - lo, np.abs(c - o)
    for f in detect_fvg(b, atr):
        m = f.idx - 1
        if m < 0 or not np.isfinite(atr[m]) or rng[m] < DISPLACEMENT_ATR * atr[m] or body[m] < DISPLACEMENT_BODY * rng[m]:
            continue
        d = 1 if f.direction == "bullish" else -1
        put("E2_fvg_displacement_1p5", d, f.idx, f.high if d > 0 else f.low, f.low if d > 0 else f.high)
    for e in weekly_breakouts(b, swings, atr, levels.week_id):
        d = 1 if e.direction == "bullish" else -1
        put("E3_broken_level_retest", d, e.idx, e.high if d > 0 else e.low, e.low if d > 0 else e.high)
    for z in detect_supply_demand(b, atr):
        d = 1 if z.kind == "demand_zone" else -1
        if htf_trend[z.idx] == d:
            put("E4_zone_pullback_d1_trend", d, z.idx, z.high if d > 0 else z.low, z.low if d > 0 else z.high)
    if tf == "H1":
        for d, i, limit, far in prev_day_sweep_reclaim(h, lo, c, levels.pdh, levels.pdl, levels.day_id):
            put("E5_prev_day_sweep_reclaim", d, i, limit, far)
    out = pl.DataFrame(rows, schema={"setup": pl.Utf8, "direction": pl.Int8, "idx": pl.Int64, "limit": pl.Float64, "far": pl.Float64})
    return out.unique(subset=["setup", "direction", "idx"], keep="first", maintain_order=True).sort("idx")
