"""Point-in-time feature matrix: row i uses only bars <= i (and events CONFIRMED by bar i)."""
import numpy as np

from app.feature_engineering.indicators import atr as atr_fn
from app.feature_engineering.indicators import ema, rolling_sum, rsi
from app.market_data.bars import Bars
from app.price_action.engine import PriceActionResult, analyze_price_action

FEATURE_NAMES = [
    "ret_1", "ret_3", "ret_5", "ret_10", "ret_20", "body", "upper_wick", "lower_wick", "atr_pct", "vol_ratio",
    "slope_20", "dist_ema50", "range_pos_50", "rsi_14", "structure_trend", "pd_position",
    "fvg_bull_20", "fvg_bear_20", "sweep_bull_20", "sweep_bear_20", "break_bull_20", "break_bear_20",
]


def _event_counts(n: int, events, direction: str, window: int) -> np.ndarray:
    x = np.zeros(n)
    for e in events:
        if e.direction == direction and e.idx < n:
            x[e.idx] += 1
    return rolling_sum(x, window)


def _pd_position(b: Bars, swings) -> np.ndarray:
    n = len(b)
    pos = np.full(n, np.nan)
    by_confirm = sorted(swings, key=lambda s: s.confirm_idx)
    hi = lo = None
    p = 0
    for i in range(n):
        while p < len(by_confirm) and by_confirm[p].confirm_idx <= i:
            s = by_confirm[p]
            if s.kind == "high":
                hi = s.price
            else:
                lo = s.price
            p += 1
        if hi is not None and lo is not None and hi > lo:
            pos[i] = np.clip((b.c[i] - lo) / (hi - lo), -0.5, 1.5)
    return pos


def compute_features(b: Bars, pa: PriceActionResult | None = None) -> tuple[list[str], np.ndarray]:
    n = len(b)
    pa = pa or analyze_price_action(b)
    a = pa.atr
    safe_a = np.where(a > 0, a, np.nan)
    cols: dict[str, np.ndarray] = {}
    for k in (1, 3, 5, 10, 20):
        r = np.full(n, np.nan)
        if n > k:
            r[k:] = (b.c[k:] - b.c[:-k]) / safe_a[k:]
        cols[f"ret_{k}"] = r
    rng = np.where(b.h - b.l > 0, b.h - b.l, np.nan)
    cols["body"] = (b.c - b.o) / rng
    cols["upper_wick"] = (b.h - np.maximum(b.o, b.c)) / rng
    cols["lower_wick"] = (np.minimum(b.o, b.c) - b.l) / rng
    cols["atr_pct"] = a / b.c
    a7, a28 = atr_fn(b.h, b.l, b.c, 7), atr_fn(b.h, b.l, b.c, 28)
    cols["vol_ratio"] = a7 / np.where(a28 > 0, a28, np.nan)
    w = 20
    slope = np.full(n, np.nan)
    if n >= w:
        x = np.arange(w) - (w - 1) / 2
        slope[w - 1:] = np.convolve(b.c, x[::-1], mode="valid") / (x ** 2).sum()
    cols["slope_20"] = slope / safe_a * w
    cols["dist_ema50"] = (b.c - ema(b.c, 50)) / safe_a
    hh = np.full(n, np.nan)
    ll = np.full(n, np.nan)
    for i in range(49, n):
        hh[i], ll[i] = b.h[i - 49:i + 1].max(), b.l[i - 49:i + 1].min()
    cols["range_pos_50"] = (b.c - ll) / np.where(hh - ll > 0, hh - ll, np.nan)
    cols["rsi_14"] = rsi(b.c, 14) / 100.0
    cols["structure_trend"] = pa.trend.astype(float)
    cols["pd_position"] = _pd_position(b, pa.swings)
    cols["fvg_bull_20"] = _event_counts(n, pa.fvgs, "bullish", 20)
    cols["fvg_bear_20"] = _event_counts(n, pa.fvgs, "bearish", 20)
    cols["sweep_bull_20"] = _event_counts(n, pa.sweeps, "bullish", 20)
    cols["sweep_bear_20"] = _event_counts(n, pa.sweeps, "bearish", 20)
    cols["break_bull_20"] = _event_counts(n, pa.breaks, "bullish", 20)
    cols["break_bear_20"] = _event_counts(n, pa.breaks, "bearish", 20)
    X = np.column_stack([cols[k] for k in FEATURE_NAMES])
    return list(FEATURE_NAMES), X
