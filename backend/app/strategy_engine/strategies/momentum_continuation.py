"""Strategy C: momentum continuation (DESIGN 4.C).

BUY (SELL mirrors): within the last 6 candles a displacement candle (body >= 1.5 ATR, close in the top 25% of its range). ADX >= 20
and rising (above its value 3 candles ago); the latest structure break is bullish and at most 12 candles old. Not exhausted: close
within 3 ATR of EMA20 and RSI <= 80. A controlled pullback after the displacement retraced at most 50% of its range. Trigger: a close
above the pullback high (market); until then a stop entry one tick above it. Invalidation: the pullback low or the displacement
midpoint, whichever is further."""
from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import (
    Candidate,
    Strategy,
    body,
    close_pos,
    fmt,
    rng,
    side,
)

LOOKBACK = 6
DISPLACEMENT_ATR = 1.5
OUTER = 0.75
MIN_ADX = 20.0
BREAK_AGE = 12
MAX_FROM_EMA_ATR = 3.0
RSI_LIMIT = 80.0
MAX_RETRACE = 0.5


class MomentumContinuation(Strategy):
    key = "momentum_continuation"
    regimes = ("TRENDING",)

    def evaluate(self, t: TFData, regime: Regime, context: Regime | None, d: int) -> Candidate:
        i, b = t.last, t.bars
        disp = [k for k in range(i - 1, i - LOOKBACK, -1)
                if body(t, k) >= DISPLACEMENT_ATR * float(t.atr[k]) and (b.c[k] - b.o[k]) * d > 0
                and (close_pos(t, k) >= OUTER if d > 0 else close_pos(t, k) <= 1 - OUTER)]
        if not disp:
            return self.no(d, f"no {side(d)} displacement candle (body >= {DISPLACEMENT_ATR} ATR) in the last {LOOKBACK - 1} candles", "forming")
        k = disp[0]
        reasons = [f"displacement candle {fmt(float(b.o[k]))} -> {fmt(float(b.c[k]))} ({body(t, k) / float(t.atr[k]):.1f} ATR body)"]
        if not (t.adx[i] >= MIN_ADX and t.adx[i] > t.adx[i - 3]):
            return self.no(d, f"momentum not confirmed: ADX {float(t.adx[i]):.0f} (needs >= {MIN_ADX:.0f} and rising)")
        brk = t.breaks_until(i)
        last_brk = brk[-1] if brk else None
        if last_brk is None or last_brk.direction != ("bullish" if d > 0 else "bearish") or last_brk.idx < i - BREAK_AGE + 1:
            return self.no(d, f"no {'bullish' if d > 0 else 'bearish'} structure break in the last {BREAK_AGE} candles")
        reasons.append(f"{last_brk.kind} {last_brk.direction} at {fmt(last_brk.price)}")
        a = float(t.atr[i])
        if abs(float(b.c[i]) - float(t.ema20[i])) > MAX_FROM_EMA_ATR * a:
            return self.no(d, f"exhausted: price is more than {MAX_FROM_EMA_ATR} ATR from EMA20 (no chase)")
        if (t.rsi[i] > RSI_LIMIT) if d > 0 else (t.rsi[i] < 100 - RSI_LIMIT):
            return self.no(d, f"exhausted: RSI {float(t.rsi[i]):.0f}")
        pull = range(k + 1, i + 1)
        ext = float(min(b.l[j] for j in pull)) if d > 0 else float(max(b.h[j] for j in pull))
        retrace = ((float(b.h[k]) - ext) if d > 0 else (ext - float(b.l[k]))) / rng(t, k)
        if retrace <= 0:
            return self.no(d, "no pullback after the displacement yet", "forming", signal_idx=k)
        if retrace > MAX_RETRACE:
            return self.no(d, f"the pullback retraced {retrace:.0%} of the displacement (maximum {MAX_RETRACE:.0%})")
        mid = (float(b.h[k]) + float(b.l[k])) / 2
        inval = min(ext, mid) if d > 0 else max(ext, mid)
        reasons.append(f"controlled pullback ({retrace:.0%} of the displacement)")
        prior = range(k + 1, i)
        if len(prior):
            trig = float(max(b.h[j] for j in prior)) if d > 0 else float(min(b.l[j] for j in prior))
            if (b.c[i] > trig) if d > 0 else (b.c[i] < trig):
                return Candidate(self.key, d, "ready", "market", float(b.c[i]), None, inval, i,
                                 f"close beyond the pullback {'high' if d > 0 else 'low'} {fmt(trig)}: enter at market", reasons)
        trig = float(max(b.h[j] for j in pull)) if d > 0 else float(min(b.l[j] for j in pull))
        return Candidate(self.key, d, "pending", "stop", trig, None, inval, i,
                         f"{side(d)} when price trades one tick {'above' if d > 0 else 'below'} the pullback {'high' if d > 0 else 'low'} {fmt(trig)}",
                         reasons)
