"""Experimental Candle Range Theory variant: higher-timeframe range raid, lower-timeframe MSS, and retest."""
import math

import numpy as np

from app.strategy_engine.context import TFData
from app.strategy_engine.regime import Regime
from app.strategy_engine.strategies.base import Candidate, Strategy, fmt, side


class CrtReversal(Strategy):
    key = "crt_reversal"
    regimes = ("TRENDING", "RANGING", "CONSOLIDATING", "UNKNOWN")

    def evaluate(self, t: TFData, regime: Regime, context: Regime | None, d: int) -> Candidate:
        return self.no(d, "CRT needs completed higher-timeframe range candles", "forming", component="htf")

    def evaluate_with_context(self, t: TFData, regime: Regime, context: Regime | None, d: int,
                              context_data: TFData | None) -> Candidate:
        if regime.label == "HIGH_VOLATILITY":
            return self.no(d, "disabled in abnormal volatility", component="regime")
        if context_data is None or not len(context_data.bars):
            return self.no(d, "CRT needs a completed higher-timeframe candle to define its range", "forming", component="htf")

        b, cb = t.bars, context_data.bars
        i, ci = t.last, context_data.last
        range_low, range_high = float(cb.l[ci]), float(cb.h[ci])
        anchor_end = int(cb.t[ci]) + int(cb.step)
        first = int(np.searchsorted(b.t, anchor_end, side="left"))
        if first > i:
            return self.no(d, "no completed signal-timeframe candles yet after the higher-timeframe range closed",
                           "forming", component="htf")

        max_age = max(1, math.ceil(int(cb.step) / int(b.step)))
        if i - first >= max_age or int(b.t[i]) - anchor_end >= int(cb.step):
            return self.no(d, "the higher-timeframe range is no longer the active CRT anchor", component="htf")
        start = max(first, i - max_age + 1)

        both_sides = [j for j in range(start, i + 1)
                      if b.l[j] < range_low and b.h[j] > range_high and range_low < b.c[j] < range_high]
        if both_sides:
            return self.no(d, "one candle swept both sides of the CRT range; direction is ambiguous", component="structure")

        swept = [j for j in range(start, i + 1)
                 if ((b.l[j] < range_low and b.c[j] > range_low) if d > 0
                     else (b.h[j] > range_high and b.c[j] < range_high))]
        if not swept:
            return self.no(d, f"no {side(d).lower()} CRT range sweep with a close back inside the range",
                           "forming", component="structure")

        kind = "high" if d > 0 else "low"
        for j in reversed(swept):
            extreme = float(b.l[j] if d > 0 else b.h[j])
            if any((b.l[k] < extreme) if d > 0 else (b.h[k] > extreme) for k in range(j + 1, i + 1)):
                continue
            swings = [s for s in t.swings_until(j, kind) if s.idx < j and range_low < s.price < range_high]
            if not swings:
                return Candidate(
                    self.key, d, "forming", invalidation=extreme, signal_idx=j,
                    reasons=[f"raid of the higher-timeframe range {fmt(range_low)}-{fmt(range_high)} closed back inside"],
                    missing=[f"no confirmed pre-raid swing {kind} inside the CRT range to define the market-structure shift"],
                ).tag(["htf"], {"anchor": ci, "range_low": range_low, "range_high": range_high, "sweep": j},
                      missing_comp="structure")

            shift = float(swings[-1].price)
            shifted = [k for k in range(j + 1, i + 1) if ((b.c[k] > shift) if d > 0 else (b.c[k] < shift))]
            reasons = [
                f"higher-timeframe candle range {fmt(range_low)}-{fmt(range_high)}",
                f"raid of the range {'low' if d > 0 else 'high'} at {fmt(extreme)} closed back inside",
            ]
            if not shifted:
                return Candidate(
                    self.key, d, "forming", invalidation=extreme, signal_idx=j, reasons=reasons,
                    missing=[f"await a lower-timeframe close {'above' if d > 0 else 'below'} the pre-raid swing {fmt(shift)}"],
                ).tag(["htf", "structure"], {"anchor": ci, "range_low": range_low, "range_high": range_high,
                                            "sweep": j, "level": shift}, missing_comp="structure")

            mss = shifted[0]
            reasons.append(f"market-structure shift: close {fmt(float(b.c[mss]))} beyond the pre-raid swing {fmt(shift)}")
            later = [k for k in range(mss + 1, i + 1) if ((b.c[k] < shift) if d > 0 else (b.c[k] > shift))]
            if later:
                return self.no(d, f"price closed back through the CRT market-structure shift at {fmt(shift)}; setup failed",
                               signal_idx=mss, component="structure")

            retests = [k for k in range(mss + 1, i + 1)
                       if ((b.l[k] <= shift) if d > 0 else (b.h[k] >= shift))]
            if retests and retests[-1] != i:
                return self.no(d, "the CRT market-structure retest already occurred; do not chase", signal_idx=mss,
                               component="entry")
            if retests:
                if not ((b.c[i] > shift) if d > 0 else (b.c[i] < shift)):
                    return self.no(d, "the CRT retest did not close back beyond the shift level", signal_idx=mss,
                                   component="entry")
                reasons.append(f"market-structure retest held at {fmt(shift)}")
                return Candidate(
                    self.key, d, "ready", "market", float(b.c[i]), None, extreme, i,
                    f"{side(d)} at market after a confirmed CRT market-structure retest", reasons,
                    targets=[(range_high if d > 0 else range_low, "CRT opposite range boundary")],
                ).tag(["htf", "structure", "structure", "entry"],
                      {"anchor": ci, "range_low": range_low, "range_high": range_high, "sweep": j,
                       "level": shift, "mss": mss, "retest": i})

            return Candidate(
                self.key, d, "pending", "limit", shift, None, extreme, mss,
                f"{side(d)} limit at {fmt(shift)} on a CRT market-structure retest", reasons,
                targets=[(range_high if d > 0 else range_low, "CRT opposite range boundary")],
            ).tag(["htf", "structure", "structure"],
                  {"anchor": ci, "range_low": range_low, "range_high": range_high, "sweep": j,
                   "level": shift, "mss": mss})

        return self.no(d, "the CRT sweep extreme was broken again before confirmation", component="structure")
