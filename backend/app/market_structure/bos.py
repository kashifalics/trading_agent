"""Break of Structure (BOS) and Change of Character (CHoCH).

Definitions (close-based, confirmed swings only):
  * A bullish break occurs on the first bar whose CLOSE is above the most recent confirmed, unbroken swing high.
  * If the prevailing trend was bearish (-1) the break is a CHoCH (character change), otherwise a BOS
    (continuation; the very first break from trend 0 is a BOS flagged initial=True).
  * Bearish breaks mirror this on swing lows.
Wicks through a level without a close beyond it are NOT breaks (they feed the liquidity-sweep detector).
"""
import numpy as np

from app.core.events import Event
from app.market_data.bars import Bars
from app.market_structure.swings import Swing


def detect_structure_breaks(b: Bars, swings: list[Swing]) -> tuple[list[Event], np.ndarray]:
    """Returns (events, trend) where trend[i] in {-1,0,1} is the structure trend known at the close of bar i."""
    n = len(b)
    by_confirm: dict[int, list[Swing]] = {}
    for s in swings:
        by_confirm.setdefault(s.confirm_idx, []).append(s)
    events: list[Event] = []
    trend = np.zeros(n, dtype=np.int8)
    cur = 0
    last_high: Swing | None = None
    last_low: Swing | None = None
    for i in range(n):
        for s in by_confirm.get(i, []):
            if s.kind == "high":
                last_high = s
            else:
                last_low = s
        if last_high is not None and b.c[i] > last_high.price:
            kind = "CHoCH" if cur == -1 else "BOS"
            events.append(Event(
                kind=kind, direction="bullish", idx=i, ts=int(b.t[i]), price=last_high.price,
                start_idx=last_high.idx, start_ts=int(b.t[last_high.idx]),
                evidence=f"close {b.c[i]:.6g} above swing high {last_high.price:.6g}"
                         + (" (reversal of bearish structure)" if kind == "CHoCH" else ""),
                meta={"swing_idx": last_high.idx, "initial": cur == 0},
            ))
            cur, last_high = 1, None
        elif last_low is not None and b.c[i] < last_low.price:
            kind = "CHoCH" if cur == 1 else "BOS"
            events.append(Event(
                kind=kind, direction="bearish", idx=i, ts=int(b.t[i]), price=last_low.price,
                start_idx=last_low.idx, start_ts=int(b.t[last_low.idx]),
                evidence=f"close {b.c[i]:.6g} below swing low {last_low.price:.6g}"
                         + (" (reversal of bullish structure)" if kind == "CHoCH" else ""),
                meta={"swing_idx": last_low.idx, "initial": cur == 0},
            ))
            cur, last_low = -1, None
        trend[i] = cur
    return events, trend


def detect_bos(b: Bars, swings: list[Swing]) -> list[Event]:
    return [e for e in detect_structure_breaks(b, swings)[0] if e.kind == "BOS"]
