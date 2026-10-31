"""Order blocks.

Bullish OB: for a bullish structure break at bar j (BOS/CHoCH) with broken swing high s, take the
lowest low in [s, j] (impulse origin, bar k). The OB is the last BEARISH candle at or before k
(within `lookback` bars). Valid only if the displacement (highest high in [k, j] - low[k]) >= min_displacement_atr * ATR.
Bearish OB mirrors. Zone = full candle range (or body if use_body).
Known at bar j. Status afterwards: fresh -> tested (price re-entered the zone) -> invalidated (a bar CLOSED through the far edge).
"""
import numpy as np

from app.core.events import Event
from app.market_data.bars import Bars


def detect_order_blocks(b: Bars, breaks: list[Event], atr: np.ndarray, lookback: int = 6,
                        min_displacement_atr: float = 1.5, use_body: bool = False) -> list[Event]:
    n = len(b)
    out: list[Event] = []
    seen: set[tuple[int, str]] = set()
    for br in breaks:
        j, s = br.idx, br.meta.get("swing_idx")
        if s is None or np.isnan(atr[j]):
            continue
        bullish = br.direction == "bullish"
        if bullish:
            k = s + int(np.argmin(b.l[s:j + 1]))
            disp = float(b.h[k:j + 1].max() - b.l[k])
            cand = [i for i in range(k, max(-1, k - lookback - 1), -1) if b.c[i] < b.o[i]]
        else:
            k = s + int(np.argmax(b.h[s:j + 1]))
            disp = float(b.h[k] - b.l[k:j + 1].min())
            cand = [i for i in range(k, max(-1, k - lookback - 1), -1) if b.c[i] > b.o[i]]
        if disp < min_displacement_atr * atr[j] or not cand:
            continue
        ob = cand[0]
        if (ob, br.direction) in seen:
            continue
        seen.add((ob, br.direction))
        lo = float(min(b.o[ob], b.c[ob]) if use_body else b.l[ob])
        hi = float(max(b.o[ob], b.c[ob]) if use_body else b.h[ob])
        status, event_idx = "fresh", None
        for m in range(j + 1, n):
            if bullish and b.c[m] < lo or (not bullish and b.c[m] > hi):
                status, event_idx = "invalidated", m
                break
            if b.l[m] <= hi and b.h[m] >= lo and status == "fresh":
                status, event_idx = "tested", m
        out.append(Event(
            kind="order_block", direction=br.direction, idx=j, ts=int(b.t[j]), low=lo, high=hi, price=(lo + hi) / 2,
            start_idx=ob, start_ts=int(b.t[ob]), status=status,
            evidence=f"last {'bearish' if bullish else 'bullish'} candle before {br.kind} ({disp / atr[j]:.1f} ATR displacement), {status}",
            params={"lookback": lookback, "min_displacement_atr": min_displacement_atr, "use_body": use_body},
            meta={"break_kind": br.kind, "status_idx": event_idx, "ob_idx": ob},
        ))
    return out
