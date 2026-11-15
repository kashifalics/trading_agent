"""Gann angles and fans (methodology 4.4) and price-time balance (4.3).

A line from anchor (t0, P0) moves r x s price units per time unit: up from a low, down from a high. r is stored as a number
("2x1" = 2 price units per time unit, steeper; "1x2" = 1 price unit per 2 time units, flatter). The scale s (price per time
unit) decides everything, so every line carries it. Squaring the range at scale s happens exactly where the 1x1 at the same
scale has moved by the range: the two are one piece of evidence, never two.
"""
import numpy as np

from app.gann.anchors import Anchor
from app.market_data.bars import Bars

RATES = (1 / 8, 1 / 4, 1 / 3, 1 / 2, 1, 2, 3, 4, 8)
LABEL = {r: (f"{int(r)}x1" if r >= 1 else f"1x{int(round(1 / r))}") for r in RATES}
S_FIXED = 1.0  # dollars per calendar day (Gann's 1 point per day; D1 only)
RETEST_WINDOW = 10


def scale_swing(prev: Anchor, a: Anchor) -> float:
    """The anchor swing's own rate: its price range over its duration in candles (its 'natural 1x1')."""
    return abs(a.price - prev.price) / max(a.idx - prev.idx, 1)


def scale_atr(atr: np.ndarray, a: Anchor) -> float:
    """One ATR per candle, measured when the anchor became known."""
    return float(atr[a.tc])


def fan(a: Anchor, scale: float, elapsed: np.ndarray, rates=RATES) -> np.ndarray:
    """Line prices, shape (len(rates), len(elapsed)); elapsed is in the scale's time unit (candles, or calendar days)."""
    sign = 1.0 if a.kind == "low" else -1.0
    e = np.asarray(elapsed, dtype=float)
    return a.price + sign * np.outer(np.asarray(rates, dtype=float) * scale, e)


def angle_events(b: Bars, a: Anchor, scale: float, r: float, tol: np.ndarray, start: int) -> dict[str, np.ndarray]:
    """touch: the candle's range reaches the line (within tol). break_: the first close beyond the line, past tol, on the side
    away from the anchor (below a rising line, above a falling one). retest: within RETEST_WINDOW candles after a break, a
    touch that closes back on the broken side. Candles before `start` carry no events."""
    n = len(b.c)
    line = fan(a, scale, np.arange(n) - a.idx, rates=(r,))[0]
    away = -1.0 if a.kind == "low" else 1.0  # broken side
    live = np.arange(n) >= start
    touch = live & (b.l <= line + tol) & (b.h >= line - tol)
    beyond = away * (b.c - line) > tol
    on_side = away * (b.c - line) <= tol
    brk = np.zeros(n, dtype=bool)
    brk[1:] = beyond[1:] & on_side[:-1]
    brk &= live
    retest = np.zeros(n, dtype=bool)
    last = -10**9
    for i in range(n):
        if brk[i]:
            last = i
            continue
        if touch[i] and 0 < i - last <= RETEST_WINDOW and away * (b.c[i] - line[i]) > 0:
            retest[i] = True
    return {"touch": touch, "break_": brk, "retest": retest}


def balance_centres(prev: Anchor, a: Anchor, scale: float) -> list[float]:
    """Time (in the scale's unit, from the start of the series) where price and time balance:
    squaring the range (elapsed = range / s) and squaring the anchor price (elapsed = P0 / s)."""
    rng = abs(a.price - prev.price)
    return [a.idx + rng / scale, a.idx + a.price / scale]
