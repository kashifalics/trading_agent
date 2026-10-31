from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.feature_engineering.indicators import atr, ema
from app.market_data.bars import Bars
from app.prediction.confidence import data_quality
from app.prediction.decision_engine import DecisionConfig, DecisionInputs, decide
from app.price_action.engine import analyze_price_action


@dataclass
class Signal:
    direction: str  # BUY | SELL
    stop_loss: float
    take_profit: float | None


class Strategy(Protocol):
    name: str
    warmup: int

    def signal(self, bars: Bars) -> Signal | None: ...


class DecisionEngineStrategy:
    """The production decision policy, restricted to price-action evidence (no analogue/ML, no MTF)
    so that every signal depends only on bars[:i+1]."""

    name = "decision_engine"

    def __init__(self, window: int = 400, cfg: DecisionConfig | None = None):
        self.window, self.cfg, self.warmup = window, cfg or DecisionConfig(), 120

    def signal(self, bars: Bars) -> Signal | None:
        b = bars.slice(max(0, len(bars) - self.window), len(bars))
        q = data_quality(n_bars=len(b), last_bar_ts=None, timeframe="1H", gap_count_recent=0, provider_status="active")
        q["score"] = 1.0 if len(b) >= 300 else q["score"]
        d = decide(DecisionInputs("BT", "bt", b, analyze_price_action(b), {"score": max(q["score"], 0.9), "issues": []}),
                   self.cfg)
        if d.decision == "WAIT" or d.plan is None:
            return None
        return Signal(d.decision, d.plan.stop_loss, d.plan.targets[0])


class MACrossStrategy:
    """Deterministic baseline: EMA(fast) crossing EMA(slow), ATR stop, fixed R target."""

    name = "ma_cross"

    def __init__(self, fast: int = 20, slow: int = 50, rr: float = 2.0, stop_atr: float = 1.5):
        self.fast, self.slow, self.rr, self.stop_atr, self.warmup = fast, slow, rr, stop_atr, slow + 15

    def signal(self, bars: Bars) -> Signal | None:
        f, s = ema(bars.c, self.fast), ema(bars.c, self.slow)
        a = atr(bars.h, bars.l, bars.c)[-1]
        if np.isnan(f[-2]) or np.isnan(s[-2]) or np.isnan(a):
            return None
        px = float(bars.c[-1])
        if f[-2] <= s[-2] and f[-1] > s[-1]:
            return Signal("BUY", px - self.stop_atr * a, px + self.rr * self.stop_atr * a)
        if f[-2] >= s[-2] and f[-1] < s[-1]:
            return Signal("SELL", px + self.stop_atr * a, px - self.rr * self.stop_atr * a)
        return None


class RandomEntryStrategy:
    """Baseline: random-direction entries (probability p per flat bar) with an ATR stop and fixed-R target."""

    name = "random_entry"

    def __init__(self, p: float = 0.02, rr: float = 2.0, stop_atr: float = 1.5, seed: int = 0):
        self.p, self.rr, self.stop_atr, self.warmup = p, rr, stop_atr, 30
        self.rng = np.random.default_rng(seed)

    def signal(self, bars: Bars) -> Signal | None:
        if self.rng.random() >= self.p:
            return None
        a = atr(bars.h, bars.l, bars.c)[-1]
        if np.isnan(a):
            return None
        px = float(bars.c[-1])
        if self.rng.random() < 0.5:
            return Signal("BUY", px - self.stop_atr * a, px + self.rr * self.stop_atr * a)
        return Signal("SELL", px + self.stop_atr * a, px - self.rr * self.stop_atr * a)


STRATEGIES = {"decision_engine": DecisionEngineStrategy, "ma_cross": MACrossStrategy, "random_entry": RandomEntryStrategy}
