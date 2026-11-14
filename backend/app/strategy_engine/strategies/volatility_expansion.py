"""Strategy F: volatility expansion (DESIGN 4.F).

BUY (SELL mirrors): in the 10 candles before an expansion candle, Bollinger width was in the lowest 15% of the last 200 candles and
ATR(5)/ATR(50) < 0.8 (compression); the box is the high/low of those 10 candles. The expansion candle's range is >= 1.8 ATR, it
closes above the box in the top 30% of its range and above the last swing high. No volume rule (spot FX and gold have no real
volume). Ready when the expansion is the last candle and the close is <= 1 ATR above the box; otherwise a limit entry at the box high
(retest). Invalidation: the box midpoint (a return there means the expansion failed)."""
from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import (
    Candidate,
    Strategy,
    close_pos,
    fmt,
    ok,
    rng,
    side,
)

LOOKBACK = 6
COMPRESSION_BARS = 10
BBW_PCT = 0.15
ATR_RATIO = 0.8
EXPANSION_ATR = 1.8
OUTER = 0.7
MAX_BEYOND_ATR = 1.0


class VolatilityExpansion(Strategy):
    key = "volatility_expansion"
    regimes = ("CONSOLIDATING", "UNKNOWN")

    def evaluate(self, t: TFData, regime: Regime, context: Regime | None, d: int) -> Candidate:
        i, b = t.last, t.bars
        for k in range(i, i - LOOKBACK, -1):
            a = float(t.atr[k - 1])
            if not a > 0 or rng(t, k) < EXPANSION_ATR * a:
                continue
            w = range(k - COMPRESSION_BARS, k)
            compressed = any(ok(t.bbw_pct[j]) and t.bbw_pct[j] <= BBW_PCT and ok(t.atr5[j]) and ok(t.atr50[j]) and t.atr50[j] > 0
                             and t.atr5[j] / t.atr50[j] < ATR_RATIO for j in w)
            if not compressed:
                continue
            box_hi, box_lo = float(b.h[k - COMPRESSION_BARS:k].max()), float(b.l[k - COMPRESSION_BARS:k].min())
            edge = box_hi if d > 0 else box_lo
            beyond = (b.c[k] > box_hi) if d > 0 else (b.c[k] < box_lo)
            outer = close_pos(t, k) >= OUTER if d > 0 else close_pos(t, k) <= 1 - OUTER
            if not (beyond and outer):
                continue
            sw = t.swings_until(k - 1, "high" if d > 0 else "low")
            if not sw or not ((b.c[k] > sw[-1].price) if d > 0 else (b.c[k] < sw[-1].price)):
                return self.no(d, f"expansion without a structure break (the last swing {fmt(sw[-1].price) if sw else '-'} holds)", "forming",
                               component="structure")
            mid = (box_hi + box_lo) / 2
            reasons = [f"compression box {fmt(box_lo)}-{fmt(box_hi)} (Bollinger width in the lowest {BBW_PCT:.0%})",
                       f"expansion candle of {rng(t, k) / a:.1f} ATR closing {'above' if d > 0 else 'below'} the box and the last swing"]
            after = b.c[k + 1:i + 1]
            if len(after) and ((after < mid).any() if d > 0 else (after > mid).any()):
                return self.no(d, f"the expansion failed: a close back past the box midpoint {fmt(mid)}", component="structure")
            ai = float(t.atr[i])
            anchors = {"expansion": k, "box_hi": box_hi, "box_lo": box_lo}
            if k == i and (float(b.c[i]) - edge) * d <= MAX_BEYOND_ATR * ai:
                return Candidate(self.key, d, "ready", "market", float(b.c[i]), None, mid, i,
                                 f"expansion close {fmt(float(b.c[i]))} within {MAX_BEYOND_ATR:g} ATR of the box: {side(d)} at market", reasons
                                 ).tag(["structure", "structure"], anchors)
            return Candidate(self.key, d, "pending", "limit", edge, None, mid, k,
                             f"{side(d)} limit at the box {'high' if d > 0 else 'low'} {fmt(edge)} (retest after the expansion)", reasons
                             ).tag(["structure", "structure"], anchors)
        return self.no(d, "no expansion candle out of a compression in the last candles", "forming", component="structure")
