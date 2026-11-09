"""Market regimes and scenario context for every candle (brief Part 6), point-in-time and scale-free.

All labels use only candles up to and including the one being labelled, and thresholds are in ATR units or trailing percentiles,
so nothing is fitted on later data and a $400 market and a $4,000 market are measured the same way. Labels are descriptive
conditions for the study (performance by regime) and features for the models; they never select a strategy by themselves.

  trend        strong/moderate/weak bullish or bearish, or none: slope of EMA50 over 20 candles in ATR, plus the 20-candle
               efficiency ratio (net move / path length)
  range        when there is no trend: tight / balanced / wide by the 50-candle range in ATR, volatile when ATR is high;
               range_breakout / failed_breakout events at the range boundary
  volatility   very_low / low / normal / high / extreme by the ATR percentile over the trailing 1,000 candles, and
               expanding / contracting / stable (ATR versus 10 candles earlier, +/- 20%)
  structure    accumulation_like / distribution_like (a range after a 100-candle decline / advance), reaccumulation_like /
               redistribution_like (a range inside a 300-candle advance / decline), trend_transition (structure trend flipped
               in the last 20 candles), or none. These are hypotheses about behaviour, never claims about who is trading.
  session      New York-time session (asia, london, overlap, new_york, rollover), pre_london (02:00-03:00 NY), weekend_reopen
               (first 2 hours after the Sunday open)
  context      near the previous day / week / month high or low (within 0.5 ATR), near a $50 level, recent spike (a candle of
               3+ ATR in the last 3), low liquidity (spread at least twice its trailing median)
"""
import numpy as np
import polars as pl

from app.feature_engineering.indicators import atr as atr_fn
from app.feature_engineering.indicators import ema
from app.gold_research.controls import session_ny
from app.patterns.candles import _roll_max, _roll_min, _sh
from app.patterns.context import Levels


def _win(x: np.ndarray, w: int, fn) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        out[w - 1:] = fn(np.lib.stride_tricks.sliding_window_view(x, w), axis=1)
    return out


def compute(t: np.ndarray, o: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr: np.ndarray, trend_struct: np.ndarray,
            levels: Levels | None = None, spread: np.ndarray | None = None) -> dict[str, np.ndarray]:
    n = len(c)
    with np.errstate(invalid="ignore", divide="ignore"):
        e50 = ema(c, 50)
        slope = (e50 - _sh(e50, 20)) / atr
        path = _win(np.abs(np.r_[0.0, np.diff(c)]), 20, np.sum)
        er = np.abs(c - _sh(c, 20)) / path
        s = np.abs(slope)
        strength = np.select([(s >= 2.0) & (er >= 0.4), s >= 1.0, s >= 0.3], ["strong", "moderate", "weak"], "")
        trend = np.where(strength == "", "none", np.char.add(strength.astype(str), np.where(slope > 0, "_bullish", "_bearish")))
        width = (_roll_max(h, 50) - _roll_min(lo, 50)) / atr
        ratio = atr / atr_fn(h, lo, c, 100)
        no_trend = trend == "none"
        rng = np.select([no_trend & (ratio > 1.25), no_trend & (width < 4), no_trend & (width > 8), no_trend],
                        ["volatile_range", "tight_range", "wide_range", "balanced_range"], "trending")
        hi50, lo50 = _sh(_roll_max(h, 50), 1), _sh(_roll_min(lo, 50), 1)
        was_range = _sh((rng != "trending").astype(float), 1) > 0
        brk_up, brk_dn = was_range & (c > hi50), was_range & (c < lo50)
        failed = np.zeros(n, dtype=bool)
        for k in (1, 2, 3):
            pu = np.r_[np.zeros(k, bool), brk_up[:-k]] if k < n else np.zeros(n, bool)
            pd = np.r_[np.zeros(k, bool), brk_dn[:-k]] if k < n else np.zeros(n, bool)
            failed |= (pu & (c < _sh(hi50, k))) | (pd & (c > _sh(lo50, k)))
        range_event = np.select([brk_up | brk_dn, failed], ["range_breakout", "failed_range_breakout"], "")
        pct = _fast_pct(atr)
        vol_level = np.select([pct < 0.1, pct < 0.3, pct <= 0.7, pct <= 0.9, pct > 0.9],
                              ["very_low", "low", "normal", "high", "extreme"], "unknown")
        chg = atr / _sh(atr, 10)
        vol_change = np.select([chg > 1.2, chg < 0.8], ["expanding", "contracting"], "stable")
        ranging = rng != "trending"
        d100 = c - _sh(c, 100)
        d300 = c - _sh(c, 300)
        flip = np.zeros(n, dtype=bool)
        ts = np.asarray(trend_struct)
        ch = np.r_[False, (ts[1:] != ts[:-1]) & (ts[1:] != 0) & (ts[:-1] != 0)]
        for k in range(20):
            flip |= np.r_[np.zeros(k, bool), ch[:n - k]]
        structural = np.select(
            [flip, ranging & (d300 > 3 * atr) & (d100 > -2 * atr), ranging & (d300 < -3 * atr) & (d100 < 2 * atr),
             ranging & (d100 < -3 * atr), ranging & (d100 > 3 * atr)],
            ["trend_transition", "reaccumulation_like", "redistribution_like", "accumulation_like", "distribution_like"], "none")
        session = session_ny(t)
        nyh = pl.Series((t.astype(np.int64) * 1_000_000).astype("datetime64[us]")).dt.replace_time_zone("UTC").dt.convert_time_zone(
            "America/New_York")
        hr, wd = nyh.dt.hour().to_numpy(), nyh.dt.weekday().to_numpy()
        pre_london = (hr >= 2) & (hr < 3)
        reopen = (wd == 7) & (hr >= 17) & (hr < 19)
        out = {"trend_regime": trend, "range_regime": rng, "range_event": range_event, "vol_level": vol_level, "vol_change": vol_change,
               "structural_regime": structural, "session": session, "pre_london": pre_london, "weekend_reopen": reopen,
               "spike": _win((h - lo) / atr >= 3, 3, np.max).astype(bool) if n >= 3 else np.zeros(n, bool)}
        near = np.full(n, "", dtype=object)
        if levels is not None:
            tags = []
            for name, hk, lk in (("day", "pdh", "pdl"), ("week", "pwh", "pwl"), ("month", "pmh", "pml")):
                hv, lv = getattr(levels, hk), getattr(levels, lk)
                tags.append(np.where(np.abs(c - hv) <= 0.5 * atr, f"prev_{name}_high", np.where(np.abs(c - lv) <= 0.5 * atr, f"prev_{name}_low", "")))
            near = np.select([t_ != "" for t_ in tags], tags, "")
        r50 = np.abs(c - np.round(c / 50) * 50) <= 0.5 * atr
        out["near_level"] = np.where(near != "", near, np.where(r50, "round_50", "none"))
        if spread is not None:
            med = pl.Series(spread).rolling_median(500, min_periods=50).to_numpy()
            out["low_liquidity"] = spread >= 2 * med
    return out


def _fast_pct(x: np.ndarray, w: int = 1000, step: int = 50) -> np.ndarray:
    """Trailing percentile with the reference window refreshed every `step` candles (still only past data): each candle is ranked
    against the sorted values of the window that ended at the last refresh point before it, plus nothing after it."""
    n = len(x)
    out = np.full(n, np.nan)
    for s in range(0, n, step):
        ref = x[max(0, s - w):s]
        ref = np.sort(ref[np.isfinite(ref)])
        if len(ref) < 200:
            continue
        seg = x[s:s + step]
        out[s:s + step] = np.searchsorted(ref, seg, side="left") / len(ref)
    return out
