"""Strategy E: liquidity-sweep reversal (DESIGN 4.E).

SELL after a sweep of highs (BUY after a sweep of lows mirrors). Meaningful levels: confirmed swing highs that are the highest point
of the 10 candles before them, the previous day's high, and equal-high clusters, all known before the sweep. Within the last 10
candles a candle traded above a level and closed back below it. Then a market-structure shift is REQUIRED: a close below the last
swing low formed before the sweep. A sweep alone is never a trade. Shift on the last candle: enter at market; earlier shift: limit
entry at the broken swing level (retest), unless price has already closed back above it. Invalidation: the sweep extreme."""
import numpy as np

from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import Candidate, Strategy, fmt, side

WINDOW = 10
SWING_EXTREME_BARS = 10


class SweepReversal(Strategy):
    key = "sweep_reversal"
    regimes = ("TRENDING", "RANGING", "CONSOLIDATING", "UNKNOWN")

    def _levels(self, t: TFData, i: int, d: int) -> list[tuple[float, str, int]]:
        """Liquidity the reversal sweeps: lows for a BUY (d = +1), highs for a SELL (d = -1), known by candle i, each with the first
        candle it is known on (a level may only be swept by a candle at or after that index: no look-ahead)."""
        b, out = t.bars, []
        kind = "low" if d > 0 else "high"
        for s in t.swings_until(i - 1, kind):
            ext = getattr(s, "_extreme10", None)  # a property of the swing alone: computed once
            if ext is None:
                lo = max(0, s.idx - SWING_EXTREME_BARS)
                ext = bool(s.price <= b.l[lo:s.idx + 1].min()) if s.kind == "low" else bool(s.price >= b.h[lo:s.idx + 1].max())
                s._extreme10 = ext
            if ext:
                out.append((float(s.price), f"swing {kind}", s.confirm_idx + 1))
        key = "pdl" if d > 0 else "pdh"
        # the previous day's level is known only once that day has closed: intraday timeframes, sweeps after the close (no look-ahead)
        pd_end = t.levels.get("pd_end")
        if t.levels.get(key) is not None and pd_end is not None and t.tf not in ("1D", "1W", "1M"):
            out.append((float(t.levels[key]), "previous day " + ("low" if d > 0 else "high"), int(np.searchsorted(b.t, int(pd_end), "left"))))
        eq = "equal_lows" if d > 0 else "equal_highs"
        for e in t.pa.equal_levels:
            if e.kind == eq and e.idx < i and e.price is not None:
                out.append((float(e.price), eq.replace("_", " "), e.idx + 1))
        return out

    def evaluate(self, t: TFData, regime: Regime, context: Regime | None, d: int) -> Candidate:
        i, b = t.last, t.bars
        if regime.label == "HIGH_VOLATILITY":
            return self.no(d, "disabled in abnormal volatility", component="regime")
        levels = self._levels(t, i, d)
        for j in range(i, i - WINDOW, -1):  # most recent sweep first
            swept = [(p, name, k) for p, name, k in levels if k <= j
                     and ((b.l[j] < p and b.c[j] > p) if d > 0 else (b.h[j] > p and b.c[j] < p))]
            if not swept:
                continue
            lvl, name, _ = (max(swept) if d > 0 else min(swept))  # the most significant level taken
            ext = float(min(b.l[j:i + 1])) if d > 0 else float(max(b.h[j:i + 1]))
            reasons = [f"sweep of the {name} {fmt(lvl)} at {fmt(float(b.l[j] if d > 0 else b.h[j]))}, closed back {'above' if d > 0 else 'below'}"]
            # the shift level is the swing that began the leg INTO the sweep: for a BUY the last swing high above the swept low
            opp = [s for s in t.swings_until(j, "high" if d > 0 else "low") if s.idx < j and ((s.price > lvl) if d > 0 else (s.price < lvl))]
            if not opp:
                return self.no(d, f"sweep of {fmt(lvl)} without a prior {'down' if d > 0 else 'up'}-leg (no swing {'above' if d > 0 else 'below'} it) "
                                  "to define the market-structure shift", "forming", component="structure")
            shift = float(opp[-1].price)
            shifted = [k for k in range(j, i + 1) if ((b.c[k] > shift) if d > 0 else (b.c[k] < shift))]
            if not shifted:
                return Candidate(self.key, d, "forming", invalidation=ext, signal_idx=j, reasons=reasons,
                                 missing=[f"market-structure shift: a close {'above' if d > 0 else 'below'} {fmt(shift)} (a sweep alone is not a trade)"]
                                 ).tag(["structure"], {"sweep": j, "level": lvl}, missing_comp="structure")
            k = shifted[0]
            reasons.append(f"market-structure shift: close {fmt(float(b.c[k]))} beyond the swing {fmt(shift)}")
            if k == i:
                return Candidate(self.key, d, "ready", "market", float(b.c[i]), None, ext, i,
                                 f"shift confirmed on the last candle: {side(d)} at market", reasons
                                 ).tag(["structure", "structure"], {"sweep": j, "level": lvl})
            if (b.c[i] < shift) if d > 0 else (b.c[i] > shift):
                return self.no(d, f"price closed back {'below' if d > 0 else 'above'} the shift level {fmt(shift)}: reversal failed", signal_idx=k,
                               component="structure")
            return Candidate(self.key, d, "pending", "limit", shift, None, ext, k,
                             f"{side(d)} limit at {fmt(shift)} on a retest of the broken swing", reasons
                             ).tag(["structure", "structure"], {"sweep": j, "level": lvl})
        return self.no(d, f"no sweep of meaningful {'lows' if d > 0 else 'highs'} in the last {WINDOW} candles", "forming", component="structure")
