"""Fair Value Gaps (three-candle imbalance).

Bullish FVG at bar i: low[i] > high[i-2]  -> zone [high[i-2], low[i]].
Bearish FVG at bar i: high[i] < low[i-2]  -> zone [high[i], low[i-2]].
Only gaps >= min_gap_atr * ATR are kept. Known at the close of bar i.
Status as of the last bar: active (untouched) | partially_filled | filled (price traded through the far edge).
"""
import numpy as np

from app.core.events import Event
from app.market_data.bars import Bars


def detect_fvg(b: Bars, atr: np.ndarray, min_gap_atr: float = 0.1, max_age: int = 500) -> list[Event]:
    n = len(b)
    out: list[Event] = []
    for i in range(2, n):
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        if b.l[i] > b.h[i - 2] and (b.l[i] - b.h[i - 2]) >= min_gap_atr * a:
            direction, lo, hi = "bullish", float(b.h[i - 2]), float(b.l[i])
        elif b.h[i] < b.l[i - 2] and (b.l[i - 2] - b.h[i]) >= min_gap_atr * a:
            direction, lo, hi = "bearish", float(b.h[i]), float(b.l[i - 2])
        else:
            continue
        status, fill_idx = "active", None
        for j in range(i + 1, min(n, i + 1 + max_age)):
            if direction == "bullish":
                if b.l[j] <= lo:
                    status, fill_idx = "filled", j
                    break
                if b.l[j] < hi:
                    status, fill_idx = "partially_filled", fill_idx if fill_idx is not None else j
            else:
                if b.h[j] >= hi:
                    status, fill_idx = "filled", j
                    break
                if b.h[j] > lo:
                    status, fill_idx = "partially_filled", fill_idx if fill_idx is not None else j
        out.append(Event(
            kind="fvg", direction=direction, idx=i, ts=int(b.t[i]), low=lo, high=hi, price=(lo + hi) / 2,
            start_idx=i - 2, start_ts=int(b.t[i - 2]), status=status,
            evidence=f"{direction} gap {lo:.6g}-{hi:.6g} ({(hi - lo) / a:.2f} ATR), {status}",
            params={"min_gap_atr": min_gap_atr}, meta={"size_atr": float((hi - lo) / a), "touch_idx": fill_idx},
        ))
    return out
