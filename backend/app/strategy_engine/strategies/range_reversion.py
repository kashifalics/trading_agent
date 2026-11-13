"""Strategy D: range mean reversion (DESIGN 4.D).

SELL at the top (BUY at the bottom mirrors): the 50 candles before the last form a range 3-12 ATR wide whose high and low are each
touched (within 0.25 ATR) by at least 2 separate swing points. Disabled when ADX >= 25 or the last close is outside the range. The
last candle reached the top 15% of the range and closed back inside with an upper wick >= 50% of its range (or an engulfing close);
RSI >= 60 and falling. Entry at market on that close. Invalidation: the range high + 0.5 ATR. Targets: midpoint, 75% across, the
opposite boundary minus 0.25 ATR."""
from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import Candidate, Strategy, fmt, rng, side

WINDOW = 50
MIN_SPAN, MAX_SPAN = 3.0, 12.0
TOUCH_ATR = 0.25
MIN_TOUCHES = 2
MAX_ADX = 25.0
EDGE = 0.15
MIN_WICK = 0.5
RSI_EDGE = 60.0
INVAL_ATR = 0.5
TARGET_INSET_ATR = 0.25


class RangeReversion(Strategy):
    key = "range_reversion"
    regimes = ("RANGING",)

    def evaluate(self, t: TFData, regime: Regime, context: Regime | None, d: int) -> Candidate:
        i, b = t.last, t.bars
        if regime.label != "RANGING":
            return self.no(d, f"disabled outside a RANGING regime (now {regime.name.lower()})")
        if t.adx[i] >= MAX_ADX:
            return self.no(d, f"disabled: ADX {float(t.adx[i]):.0f} >= {MAX_ADX:.0f} (trend developing)")
        a = float(t.atr[i])
        hi, lo = float(b.h[i - WINDOW:i].max()), float(b.l[i - WINDOW:i].min())
        span = hi - lo
        if not (MIN_SPAN * a <= span <= MAX_SPAN * a):
            return self.no(d, f"range span {span / a:.1f} ATR is outside {MIN_SPAN:g}-{MAX_SPAN:g} ATR")
        if not (lo <= b.c[i] <= hi):
            return self.no(d, f"disabled: the last close is outside the range {fmt(lo)}-{fmt(hi)} (breakout)")
        sw = [s for s in t.swings_until(i) if s.idx >= i - WINDOW]
        top = sum(1 for s in sw if s.kind == "high" and abs(s.price - hi) <= TOUCH_ATR * a)
        bot = sum(1 for s in sw if s.kind == "low" and abs(s.price - lo) <= TOUCH_ATR * a)
        if top < MIN_TOUCHES or bot < MIN_TOUCHES:
            return self.no(d, f"range not established: {top} touches of the high and {bot} of the low (>= {MIN_TOUCHES} each needed)", "forming")
        reasons = [regime.reason, f"range {fmt(lo)}-{fmt(hi)} ({span / a:.1f} ATR), {top} touches of the high and {bot} of the low"]
        at_edge = (b.l[i] <= lo + EDGE * span) if d > 0 else (b.h[i] >= hi - EDGE * span)
        if not at_edge:
            return self.no(d, f"price is not at the range {'low' if d > 0 else 'high'} (needs the {'bottom' if d > 0 else 'top'} 15%)", "forming")
        o, c, h, low = float(b.o[i]), float(b.c[i]), float(b.h[i]), float(b.l[i])
        wick = (min(o, c) - low) if d > 0 else (h - max(o, c))
        engulf = (c > o and c >= float(b.h[i - 1])) if d > 0 else (c < o and c <= float(b.l[i - 1]))
        if not (wick >= MIN_WICK * rng(t, i) or engulf):
            return self.no(d, f"no rejection at the range {'low' if d > 0 else 'high'} (needs a {'lower' if d > 0 else 'upper'} wick >= 50% or an engulfing close)",
                           "forming")
        r0, r1 = float(t.rsi[i - 1]), float(t.rsi[i])
        exhausted = (r0 <= 100 - RSI_EDGE and r1 > r0) if d > 0 else (r0 >= RSI_EDGE and r1 < r0)
        if not exhausted:
            return self.no(d, f"no exhaustion: RSI {r1:.0f} (needs {'<= 40 and rising' if d > 0 else '>= 60 and falling'})", "forming")
        mid = (hi + lo) / 2
        far = lo + 0.75 * span if d > 0 else hi - 0.75 * span
        opp = hi - TARGET_INSET_ATR * a if d > 0 else lo + TARGET_INSET_ATR * a
        inval = (lo - INVAL_ATR * a) if d > 0 else (hi + INVAL_ATR * a)
        return Candidate(self.key, d, "ready", "market", c, None, inval, i,
                         f"rejection of the range {'low' if d > 0 else 'high'} closed back inside: {side(d)} at market",
                         reasons + ["rejection candle and RSI exhaustion"], [],
                         [(mid, "range midpoint"), (far, "75% across the range"), (opp, "opposite range boundary")])
