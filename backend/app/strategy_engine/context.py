"""One signal timeframe's complete candles with every indicator the regime classifier and the strategies use (computed once)."""
from dataclasses import dataclass, field

import numpy as np

from app.feature_engineering.indicators import (
    adx,
    atr,
    bollinger_width,
    efficiency_ratio,
    ema,
    rsi,
    trailing_percentile,
)
from app.market_data.bars import Bars
from app.price_action.engine import PriceActionResult, analyze_price_action


@dataclass
class TFData:
    tf: str
    bars: Bars
    pa: PriceActionResult
    atr: np.ndarray
    adx: np.ndarray
    pdi: np.ndarray
    mdi: np.ndarray
    ema20: np.ndarray
    ema50: np.ndarray
    rsi: np.ndarray
    bbw: np.ndarray
    bbw_pct: np.ndarray
    er: np.ndarray
    atr_pct: np.ndarray
    atr5: np.ndarray
    atr50: np.ndarray
    levels: dict = field(default_factory=dict)  # previous day / week high and low, when known (service.py)

    @property
    def n(self) -> int:
        return len(self.bars)

    @property
    def last(self) -> int:
        return len(self.bars) - 1

    @classmethod
    def build(cls, tf: str, bars: Bars, pa: PriceActionResult | None = None, levels: dict | None = None) -> "TFData":
        h, lo, c = bars.h.astype(float), bars.l.astype(float), bars.c.astype(float)
        a = atr(h, lo, c, 14)
        ax, pdi, mdi = adx(h, lo, c, 14)
        bbw = bollinger_width(c, 20, 2.0)
        return cls(tf=tf, bars=bars, pa=pa if pa is not None else analyze_price_action(bars), atr=a, adx=ax, pdi=pdi, mdi=mdi,
                   ema20=ema(c, 20), ema50=ema(c, 50), rsi=rsi(c, 14), bbw=bbw, bbw_pct=trailing_percentile(bbw, 200, 50),
                   er=efficiency_ratio(c, 20), atr_pct=trailing_percentile(a, 200, 50), atr5=atr(h, lo, c, 5), atr50=atr(h, lo, c, 50),
                   levels=levels or {})

    def swings_until(self, i: int, kind: str | None = None):
        """Swings confirmed by bar i (never later information)."""
        return [s for s in self.pa.swings if s.confirm_idx <= i and (kind is None or s.kind == kind)]

    def breaks_until(self, i: int):
        return [e for e in self.pa.breaks if e.idx <= i]
