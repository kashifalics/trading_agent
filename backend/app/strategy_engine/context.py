"""One signal timeframe's complete candles with every indicator the regime classifier and the strategies use (computed once)."""
from dataclasses import dataclass, field, replace
from types import SimpleNamespace

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
    _last: int | None = None  # a view of the history as of this candle (research replay); None = the latest candle

    @property
    def n(self) -> int:
        return self.last + 1

    @property
    def last(self) -> int:
        return len(self.bars) - 1 if self._last is None else self._last

    @classmethod
    def build(cls, tf: str, bars: Bars, pa: PriceActionResult | None = None, levels: dict | None = None) -> "TFData":
        h, lo, c = bars.h.astype(float), bars.l.astype(float), bars.c.astype(float)
        a = atr(h, lo, c, 14)
        ax, pdi, mdi = adx(h, lo, c, 14)
        bbw = bollinger_width(c, 20, 2.0)
        pa = pa if pa is not None else analyze_price_action(bars)
        mark_zone_lifetimes(pa, c)
        return cls(tf=tf, bars=bars, pa=pa, atr=a, adx=ax, pdi=pdi, mdi=mdi,
                   ema20=ema(c, 20), ema50=ema(c, 50), rsi=rsi(c, 14), bbw=bbw, bbw_pct=trailing_percentile(bbw, 200, 50),
                   er=efficiency_ratio(c, 20), atr_pct=trailing_percentile(a, 200, 50), atr5=atr(h, lo, c, 5), atr50=atr(h, lo, c, 50),
                   levels=levels or {})

    def at(self, i: int, window: int = 500, levels: dict | None = None) -> "TFData":
        """The same history as it was known at the close of candle i: indicators and events up to i only, events limited to the
        last `window` candles (the live engine sees 500 candles). Used to replay the engine over history without look-ahead."""
        if not hasattr(self, "_index"):
            self._index = {name: (np.array([_key(e) for e in getattr(self.pa, name)], dtype=np.int64), getattr(self.pa, name))
                           for name in EVENT_LISTS}
        sub = {}
        for name, (keys, items) in self._index.items():
            a, b = np.searchsorted(keys, i - window, "left"), np.searchsorted(keys, i, "right")
            sub[name] = items[a:b]
        pa = SimpleNamespace(trend=self.pa.trend, atr=self.pa.atr, **sub)
        return replace(self, pa=pa, _last=i, levels=self.levels if levels is None else levels)

    def swings_until(self, i: int, kind: str | None = None):
        """Swings confirmed by bar i (never later information)."""
        return [s for s in self.pa.swings if s.confirm_idx <= i and (kind is None or s.kind == kind)]

    def breaks_until(self, i: int):
        return [e for e in self.pa.breaks if e.idx <= i]


WINDOW = 500  # candles of history the live engine sees (and a replay view keeps)
EVENT_LISTS = ("swings", "breaks", "equal_levels", "order_blocks", "fvgs", "zones")
ZONE_LISTS = ("order_blocks", "fvgs", "zones", "breakers")


def _key(e) -> int:
    return int(e.confirm_idx) if hasattr(e, "confirm_idx") else int(e.idx)


def mark_zone_lifetimes(pa: PriceActionResult, c: np.ndarray) -> None:
    """meta['dead_from'] = the first candle after a zone formed whose close is beyond its far edge (a bullish zone closed below its low,
    a bearish one above its high). 'Alive at i' is then dead_from > i: causal, unlike a status computed from the whole history."""
    n = len(c)
    for name in ZONE_LISTS:
        for z in getattr(pa, name, []) or []:
            if "dead_from" in z.meta or z.low is None or z.high is None:
                continue
            seg = c[z.idx + 1:]
            hit = (seg < z.low) if z.direction == "bullish" else (seg > z.high) if z.direction == "bearish" else np.zeros(0, bool)
            k = int(np.argmax(hit)) if hit.any() else -1
            z.meta["dead_from"] = z.idx + 1 + k if k >= 0 else n + 10**9


def alive(z, i: int) -> bool:
    return z.meta.get("dead_from", 10**12) > i
