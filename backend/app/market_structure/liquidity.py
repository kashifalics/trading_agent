"""Equal highs/lows and liquidity sweeps.

  * Equal highs (lows): two confirmed swing highs (lows) within tol_atr * ATR of each other, the
    earlier one still un-exceeded. Known at the confirm index of the later swing.
  * Liquidity sweep: a bar whose wick trades beyond a resting level (swing high/low) but CLOSES back
    inside. Bearish sweep = wick above a high, close below it. Bullish sweep mirrors on lows.
    A level is consumed by the first bar that trades through it, sweep or not.
"""
import numpy as np

from app.core.events import Event
from app.market_data.bars import Bars
from app.market_structure.swings import Swing


def detect_equal_levels(b: Bars, swings: list[Swing], atr: np.ndarray, tol_atr: float = 0.1,
                        max_age: int = 200) -> list[Event]:
    out: list[Event] = []
    for kind in ("high", "low"):
        ss = [s for s in swings if s.kind == kind]
        for j, s in enumerate(ss):
            a = atr[s.confirm_idx] if s.confirm_idx < len(atr) else np.nan
            if np.isnan(a):
                continue
            for p in ss[:j]:
                if s.idx - p.idx > max_age or s.idx == p.idx:
                    continue
                if abs(s.price - p.price) > tol_atr * a:
                    continue
                seg = b.h[p.idx + 1:s.idx] if kind == "high" else b.l[p.idx + 1:s.idx]
                exceeded = len(seg) and ((seg.max() > max(s.price, p.price)) if kind == "high" else (seg.min() < min(s.price, p.price)))
                if exceeded:
                    continue
                lvl = (s.price + p.price) / 2
                out.append(Event(
                    kind=f"equal_{kind}s", direction="bearish" if kind == "high" else "bullish", idx=s.confirm_idx,
                    ts=int(b.t[s.confirm_idx]), price=lvl, start_idx=p.idx, start_ts=int(b.t[p.idx]),
                    evidence=f"swing {kind}s at {p.price:.6g} and {s.price:.6g} within {tol_atr} ATR",
                    meta={"level_idx": [p.idx, s.idx]},
                    params={"tol_atr": tol_atr},
                ))
                break
    out.sort(key=lambda e: e.idx)
    return out


def detect_liquidity_sweeps(b: Bars, swings: list[Swing], max_age: int = 150) -> list[Event]:
    out: list[Event] = []
    by_confirm: dict[int, list[Swing]] = {}
    for s in swings:
        by_confirm.setdefault(s.confirm_idx, []).append(s)
    highs: list[Swing] = []
    lows: list[Swing] = []
    for i in range(len(b)):
        for s in by_confirm.get(i, []):
            (highs if s.kind == "high" else lows).append(s)
        for lvl in list(highs):
            if i - lvl.idx > max_age:
                highs.remove(lvl)
            elif b.h[i] > lvl.price and i > lvl.confirm_idx - 1 and i >= lvl.confirm_idx:
                if b.c[i] < lvl.price:
                    out.append(Event(
                        kind="liquidity_sweep", direction="bearish", idx=i, ts=int(b.t[i]), price=lvl.price,
                        high=float(b.h[i]), low=float(b.l[i]), start_idx=lvl.idx, start_ts=int(b.t[lvl.idx]),
                        evidence=f"wick to {b.h[i]:.6g} above swing high {lvl.price:.6g}, closed back at {b.c[i]:.6g}",
                        meta={"side": "buy_side_liquidity"}))
                highs.remove(lvl)
        for lvl in list(lows):
            if i - lvl.idx > max_age:
                lows.remove(lvl)
            elif b.l[i] < lvl.price and i >= lvl.confirm_idx:
                if b.c[i] > lvl.price:
                    out.append(Event(
                        kind="liquidity_sweep", direction="bullish", idx=i, ts=int(b.t[i]), price=lvl.price,
                        high=float(b.h[i]), low=float(b.l[i]), start_idx=lvl.idx, start_ts=int(b.t[lvl.idx]),
                        evidence=f"wick to {b.l[i]:.6g} below swing low {lvl.price:.6g}, closed back at {b.c[i]:.6g}",
                        meta={"side": "sell_side_liquidity"}))
                lows.remove(lvl)
    return out
