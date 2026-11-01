"""The opportunity engine's setup rules as a backtestable strategy.

It calls exactly `generate_setup` (the same function the live scan uses) with a higher-timeframe bias built, point-in-time, by
resampling the strategy's own history into the style's bias timeframe(s). A trade is opened only on a FRESH trigger (the confirming
event is on the latest bar), at the next bar's open, with the setup's structural stop and TP1. The evidence score and analogue search are
NOT part of this replay (they would need a model of their own); this validates the rule set that produces the setups.
Deliberate simplifications, all listed in docs/STRATEGY_VALIDATION.md: UTC-aligned daily/weekly resampling, no calendar-month bias
timeframes (1W entries have no higher-timeframe filter), entries are market orders at the next open.
"""
import numpy as np

from app.backtesting.strategies import STRATEGIES, Signal
from app.market_data.bars import Bars
from app.market_data.timeframes import TIMEFRAMES
from app.multi_timeframe.alignment import alignment, build_view
from app.opportunities.config import BIAS_TFS, PROFILES, round_trip_cost
from app.opportunities.setup import Bias, compute_concepts, generate_setup
from app.price_action.engine import analyze_price_action

WEEK_OFFSET = 4 * 86400  # epoch day 0 is a Thursday; shift so weeks start on Monday
FIXED = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1H": 3600, "2H": 7200, "4H": 14400, "1D": 86400, "1W": 604800}


def resample(b: Bars, seconds: int) -> Bars:
    """Completed higher-timeframe bars from `b` (a bucket is used only once its end is <= the end of the last base bar)."""
    if len(b) == 0 or seconds <= b.step:
        return b.slice(0, 0)
    off = WEEK_OFFSET if seconds == 604800 else 0
    key = (b.t - off) // seconds
    starts = np.r_[0, np.flatnonzero(np.diff(key)) + 1]
    ends = np.r_[starts[1:], len(b)]
    hi, lo = np.maximum.reduceat(b.h, starts), np.minimum.reduceat(b.l, starts)  # computed per FULL bucket before any is dropped
    bucket_start = key[starts] * seconds + off
    keep = bucket_start + seconds <= int(b.t[-1]) + b.step  # drop buckets that are still forming
    if not keep.any():
        return b.slice(0, 0)
    return Bars(t=bucket_start[keep].astype(np.int64), o=b.o[starts][keep], h=hi[keep], l=lo[keep], c=b.c[ends - 1][keep],
                v=np.full(int(keep.sum()), np.nan), step=seconds)


class OpportunityRulesStrategy:
    """Opportunity-engine setup rules (see module docstring)."""

    name = "opportunity_rules"

    def __init__(self, style: str = "swing", symbol: str = "BTCUSDT", window: int = 500, htf_window: int = 4000):
        self.prof, self.symbol, self.window, self.htf_window = PROFILES[style], symbol, window, htf_window
        self.cost = round_trip_cost(symbol)
        self.warmup = 150
        self._tf_by_step = {v: k for k, v in FIXED.items()}
        self._view_cache: dict[tuple[str, int, int], object] = {}  # (tf, n completed HTF bars, last HTF open) -> view (pure function of those bars)

    def _bias(self, bars: Bars) -> Bias:
        tf = self._tf_by_step.get(bars.step)
        views = []
        base = bars.slice(max(0, len(bars) - self.htf_window), len(bars))
        for role, code in zip(("higher", "intermediate"), reversed(BIAS_TFS.get(tf, ()))):
            sec = FIXED.get(code)  # calendar-month timeframes are not available to this replay
            if not sec:
                continue
            h = resample(base, sec)
            if len(h) >= 40:
                k = (code, len(h), int(h.t[-1]), role)
                if k not in self._view_cache:  # structure only changes when a new higher-timeframe bar completes
                    if len(self._view_cache) > 64:
                        self._view_cache.clear()
                    self._view_cache[k] = build_view(h, code, role)[0]
                views.append(self._view_cache[k])
        al = alignment(views) if views else {"score": 0.0, "conflict": False, "direction": 0, "views": []}
        return Bias(int(al["direction"]), float(al["score"]), bool(al["conflict"]), al.get("views", []))

    def signal(self, bars: Bars) -> Signal | None:
        n = len(bars)
        b = bars.slice(max(0, n - self.window), n)
        pa = analyze_price_action(b)
        out = generate_setup(b, pa, compute_concepts(b, pa), self._bias(bars), self.prof, self.cost)
        s = out.setup
        if s is None or s.status != "entry_triggered" or s.trigger_ts != int(b.t[-1]):
            return None
        return Signal(s.direction, s.stop_loss, s.targets[0]["price"])


STRATEGIES["opportunity_rules"] = OpportunityRulesStrategy  # type: ignore[assignment]  (registered only when this module is imported)
__all__ = ["OpportunityRulesStrategy", "resample", "TIMEFRAMES"]
