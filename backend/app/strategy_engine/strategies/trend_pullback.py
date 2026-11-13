"""Strategy A: trend-following pullback (DESIGN 4.A).

BUY (SELL mirrors): the timeframe is TRENDING up, structure is bullish and the context timeframe is not trending down. Within the last
8 candles price pulled back to within 0.3 ATR of EMA20, or into an unmitigated bullish order block / FVG / demand zone, without closing
more than 0.5 ATR below EMA50. Momentum recovered (RSI back above 50 within 3 candles, or a close above the prior high). Trigger: a
close above the high of the deepest pullback candle (market entry); until then a stop entry one tick above that high. Invalidation:
the pullback low."""
import numpy as np

from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import Candidate, Strategy, fmt, side

WINDOW = 8
NEAR_EMA_ATR = 0.3
DEPTH_EMA50_ATR = 0.5
DEAD = ("invalidated", "broken", "filled")
MAX_ZONE_ATR = 2.0  # a zone wider than this (e.g. a gap over a market close) is not a precise pullback area


class TrendPullback(Strategy):
    key = "trend_pullback"
    regimes = ("TRENDING",)

    def evaluate(self, t: TFData, regime: Regime, context: Regime | None, d: int) -> Candidate:
        i = t.last
        b = t.bars
        if regime.label != "TRENDING" or regime.direction != d:
            return self.no(d, f"needs a {'rising' if d > 0 else 'falling'} TRENDING regime (now {regime.out()['name'].lower()})")
        if int(t.pa.trend[i]) != d:
            return self.no(d, f"market structure is not {'bullish' if d > 0 else 'bearish'}")
        if context is not None and context.label == "TRENDING" and context.direction == -d:
            return self.no(d, "the context timeframe trends the other way")
        a = float(t.atr[i])
        lo, hi = i - WINDOW + 1, i
        zones = [z for z in (t.pa.order_blocks + t.pa.fvgs + t.pa.zones)
                 if z.direction == ("bullish" if d > 0 else "bearish") and z.idx < lo and (z.status or "") not in DEAD
                 and z.low is not None and z.high is not None and (z.high - z.low) <= MAX_ZONE_ATR * a]  # no session-gap "zones"
        touched, where = None, ""
        for j in range(lo, hi + 1):
            ext = float(b.l[j]) if d > 0 else float(b.h[j])
            if abs(ext - float(t.ema20[j])) <= NEAR_EMA_ATR * a or (d > 0 and ext < t.ema20[j]) or (d < 0 and ext > t.ema20[j]):
                touched, where = j, f"EMA20 ({fmt(float(t.ema20[j]))})"
            for z in zones:
                if z.low - NEAR_EMA_ATR * a <= ext <= z.high + NEAR_EMA_ATR * a:
                    touched, where = j, f"{z.kind.replace('_', ' ')} {fmt(z.low)}-{fmt(z.high)}"
        if touched is None:
            return self.no(d, f"no pullback to EMA20 or a {'bullish' if d > 0 else 'bearish'} zone in the last {WINDOW} candles", "forming")
        closes = b.c[lo:hi + 1].astype(float)
        e50 = t.ema50[lo:hi + 1]
        if (d > 0 and (closes < e50 - DEPTH_EMA50_ATR * a).any()) or (d < 0 and (closes > e50 + DEPTH_EMA50_ATR * a).any()):
            return self.no(d, "the pullback closed more than 0.5 ATR beyond EMA50: the trend is in doubt")
        seg = b.l[lo:hi + 1] if d > 0 else b.h[lo:hi + 1]
        k = lo + int(np.argmin(seg) if d > 0 else np.argmax(seg))  # deepest pullback candle
        inval = float(b.l[k]) if d > 0 else float(b.h[k])
        r = t.rsi
        crossed = any(np.isfinite(r[j]) and np.isfinite(r[j - 1]) and ((r[j - 1] < 50 <= r[j]) if d > 0 else (r[j - 1] > 50 >= r[j]))
                      for j in range(i - 2, i + 1))
        beyond_prev = (b.c[i] > b.h[i - 1]) if d > 0 else (b.c[i] < b.l[i - 1])
        reasons = [regime.reason, f"pullback to {where}", f"deepest pullback candle {fmt(inval)}"]
        trig_level = float(b.h[k]) if d > 0 else float(b.l[k])
        if not (crossed or beyond_prev):
            return Candidate(self.key, d, "forming", invalidation=inval, signal_idx=i, reasons=reasons,
                             missing=[f"momentum recovery: RSI back {'above' if d > 0 else 'below'} 50, or a close beyond the prior candle"])
        reasons.append("momentum recovered" + (" (RSI crossed 50)" if crossed else " (close beyond the prior candle)"))
        if k < i and ((b.c[i] > trig_level) if d > 0 else (b.c[i] < trig_level)):
            return Candidate(self.key, d, "ready", "market", float(b.c[i]), None, inval, i,
                             f"continuation close beyond the pullback {'high' if d > 0 else 'low'} {fmt(trig_level)}: enter at market", reasons)
        return Candidate(self.key, d, "pending", "stop", trig_level, None, inval, i,
                         f"{side(d)} when price trades one tick {'above' if d > 0 else 'below'} {fmt(trig_level)} (continuation trigger)", reasons)
