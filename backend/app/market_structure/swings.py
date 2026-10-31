"""Swing highs/lows without look-ahead.

A swing high at index i needs `right` later bars to exist; it is therefore only KNOWN at
confirm_idx = i + right. Consumers must filter on confirm_idx <= current bar.
"""
from dataclasses import dataclass

from app.market_data.bars import Bars


@dataclass
class Swing:
    idx: int
    kind: str  # high | low
    price: float
    confirm_idx: int
    label: str | None = None  # HH | LH | HL | LL (vs previous swing of the same kind)


def find_swings(b: Bars, left: int = 3, right: int = 3) -> list[Swing]:
    """Swing high: strictly higher than `left` bars before and `right` bars after (mirror for lows)."""
    n = len(b)
    swings: list[Swing] = []
    for i in range(left, n - right):
        hi, lo = b.h[i], b.l[i]
        if hi > b.h[i - left:i].max() and hi > b.h[i + 1:i + right + 1].max():
            swings.append(Swing(i, "high", float(hi), i + right))
        if lo < b.l[i - left:i].min() and lo < b.l[i + 1:i + right + 1].min():
            swings.append(Swing(i, "low", float(lo), i + right))
    swings.sort(key=lambda s: (s.confirm_idx, s.idx))
    prev: dict[str, Swing] = {}
    for s in swings:  # label in order of confirmation
        p = prev.get(s.kind)
        if p:
            if s.kind == "high":
                s.label = "HH" if s.price > p.price else "LH"
            else:
                s.label = "HL" if s.price > p.price else "LL"
        prev[s.kind] = s
    return swings


def confirmed(swings: list[Swing], idx: int) -> list[Swing]:
    return [s for s in swings if s.confirm_idx <= idx]


def structure_bias(swings: list[Swing], idx: int) -> int:
    """+1 if the last two confirmed swing highs AND lows are rising (HH+HL), -1 if falling (LH+LL), else 0."""
    c = confirmed(swings, idx)
    highs = [s for s in c if s.kind == "high"][-2:]
    lows = [s for s in c if s.kind == "low"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return 0
    up = highs[1].price > highs[0].price and lows[1].price > lows[0].price
    down = highs[1].price < highs[0].price and lows[1].price < lows[0].price
    return 1 if up else -1 if down else 0
