"""Supply/demand zones from base-and-impulse.

Base: 1..max_base consecutive bars each with range <= base_atr * ATR. Impulse: the next bar has
range >= impulse_atr * ATR, body >= 60% of its range, and closes beyond the base extreme.
Demand if the impulse is up (zone = base low..high), supply if down. Known at the impulse bar's close.
Status afterwards: fresh | tested (price re-entered zone) | broken (close through distal edge).
"""
import numpy as np

from app.core.events import Event
from app.market_data.bars import Bars


def detect_supply_demand(b: Bars, atr: np.ndarray, base_atr: float = 0.8, impulse_atr: float = 1.5,
                         max_base: int = 3) -> list[Event]:
    n = len(b)
    out: list[Event] = []
    skip_until = -1
    for i in range(1, n):
        a = atr[i - 1]
        if np.isnan(a) or a <= 0 or i <= skip_until:
            continue
        rng = b.h[i] - b.l[i]
        body = abs(b.c[i] - b.o[i])
        if rng < impulse_atr * a or body < 0.6 * rng:
            continue
        # walk back over base bars
        j = i - 1
        while j >= 0 and i - j <= max_base and (b.h[j] - b.l[j]) <= base_atr * a:
            j -= 1
        base_start = j + 1
        if base_start > i - 1:
            continue
        lo, hi = float(b.l[base_start:i].min()), float(b.h[base_start:i].max())
        up = b.c[i] > b.o[i] and b.c[i] > hi
        dn = b.c[i] < b.o[i] and b.c[i] < lo
        if not (up or dn):
            continue
        direction = "bullish" if up else "bearish"
        status = "fresh"
        for m in range(i + 1, n):
            if (up and b.c[m] < lo) or (dn and b.c[m] > hi):
                status = "broken"
                break
            if b.l[m] <= hi and b.h[m] >= lo and status == "fresh":
                status = "tested"
        out.append(Event(
            kind="demand_zone" if up else "supply_zone", direction=direction, idx=i, ts=int(b.t[i]), low=lo, high=hi,
            price=(lo + hi) / 2, start_idx=base_start, start_ts=int(b.t[base_start]), status=status,
            evidence=f"{i - base_start}-bar base {lo:.6g}-{hi:.6g} then {rng / a:.1f} ATR {'up' if up else 'down'} impulse, {status}",
            params={"base_atr": base_atr, "impulse_atr": impulse_atr, "max_base": max_base},
        ))
        skip_until = i
    return out
