"""Strategy B: breakout and retest (DESIGN 4.B).

BUY (SELL mirrors): a box of 20 candles ending 1-15 candles ago spans at most 6 ATR. A later candle closed at least 0.25 ATR above
the box high with a body of at least 60% of its range. No close back inside the box since then (that would be a false breakout).
Price is at most 2 ATR above the level (no chasing). A retest candle touched within 0.3 ATR of the level and closed above it: if
that is the last candle, enter at market; otherwise a limit entry 0.1 ATR above the level. Invalidation: the level minus 0.5 ATR."""
from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import (
    Candidate,
    Strategy,
    body,
    fmt,
    rng,
    side,
)

BOX = 20
MAX_AGE = 15
MAX_SPAN_ATR = 6.0
BREAK_ATR = 0.25
MIN_BODY = 0.6
MAX_TRAVEL_ATR = 2.0
RETEST_ATR = 0.3
LIMIT_OFFSET_ATR = 0.1
INVAL_ATR = 0.5


class BreakoutRetest(Strategy):
    key = "breakout_retest"
    regimes = ("RANGING", "CONSOLIDATING", "TRENDING", "UNKNOWN")

    def evaluate(self, t: TFData, regime: Regime, context: Regime | None, d: int) -> Candidate:
        i, b = t.last, t.bars
        for k in range(i, max(BOX, i - MAX_AGE + 1) - 1, -1):  # most recent breakout first
            a = float(t.atr[k - 1])
            box_hi, box_lo = float(b.h[k - BOX:k].max()), float(b.l[k - BOX:k].min())
            if not a > 0 or (box_hi - box_lo) > MAX_SPAN_ATR * a:
                continue
            level = box_hi if d > 0 else box_lo
            broke = (b.c[k] > level + BREAK_ATR * a) if d > 0 else (b.c[k] < level - BREAK_ATR * a)
            if not broke or body(t, k) < MIN_BODY * rng(t, k):
                continue
            reasons = [f"{BOX}-candle box {fmt(box_lo)}-{fmt(box_hi)} ({(box_hi - box_lo) / a:.1f} ATR)",
                       f"breakout close {fmt(float(b.c[k]))} {'above' if d > 0 else 'below'} {fmt(level)} with a strong body"]
            after = b.c[k + 1:i + 1]
            if len(after) and ((after < level).any() if d > 0 else (after > level).any()):
                return self.no(d, f"false breakout: a close back inside the box after the break of {fmt(level)}", component="structure")
            ai = float(t.atr[i])
            travel = (float(b.c[i]) - level) * d / ai
            if travel > MAX_TRAVEL_ATR:
                return self.no(d, f"price has travelled {travel:.1f} ATR from the broken level {fmt(level)} (limit {MAX_TRAVEL_ATR}): no chase",
                               signal_idx=k)
            inval = level - d * INVAL_ATR * ai
            retests = [j for j in range(k + 1, i + 1)
                       if ((b.l[j] <= level + RETEST_ATR * ai and b.c[j] > level) if d > 0 else (b.h[j] >= level - RETEST_ATR * ai and b.c[j] < level))]
            anchors = {"breakout": k, "retest": retests, "level": level}
            if retests and retests[-1] == i:
                return Candidate(self.key, d, "ready", "market", float(b.c[i]), None, inval, i,
                                 f"retest of {fmt(level)} held on the last candle: enter at market", reasons + ["retest held"]
                                 ).tag(["structure", "structure", "entry"], anchors)
            entry = level + d * LIMIT_OFFSET_ATR * ai
            return Candidate(self.key, d, "pending", "limit", entry, (min(level, entry), max(level, entry)), inval, k,
                             f"{side(d)} limit at {fmt(entry)} on a retest of the broken level {fmt(level)}", reasons
                             ).tag(["structure", "structure"], anchors)
        return self.no(d, f"no {BOX}-candle box broken with a strong close in the last {MAX_AGE} candles", "forming", component="structure")
