"""Float64 columnar view of candles for analysis code (storage stays Decimal)."""
from collections import Counter
from dataclasses import dataclass

import numpy as np

from app.market_data.types import Candle


@dataclass
class Bars:
    t: np.ndarray  # int64 epoch seconds, candle OPEN time
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray  # noqa: E741
    c: np.ndarray
    v: np.ndarray
    step: int  # nominal seconds per bar
    vtype: str = "none"  # what v measures: base (exchange volume) | tick (broker price updates) | venue (Dukascopy) | none
    tb: np.ndarray | None = None  # taker-buy volume per bar (Binance only); None when the source does not report it

    def __len__(self) -> int:
        return len(self.t)

    @classmethod
    def from_candles(cls, candles: list[Candle], step: int, include_incomplete: bool = False) -> "Bars":
        rows = [c for c in candles if include_incomplete or c.complete]
        rows.sort(key=lambda c: c.ts)
        vtype = Counter(c.volume_type or "none" for c in rows).most_common(1)[0][0] if rows else "none"
        tb = np.array([float(c.meta["taker_buy_base"]) for c in rows]) \
            if rows and all((c.meta or {}).get("taker_buy_base") is not None for c in rows) else None
        return cls(
            t=np.array([int(c.ts.timestamp()) for c in rows], dtype=np.int64),
            o=np.array([float(c.open) for c in rows]),
            h=np.array([float(c.high) for c in rows]),
            l=np.array([float(c.low) for c in rows]),
            c=np.array([float(c.close) for c in rows]),
            v=np.array([float(c.volume) if c.volume is not None else np.nan for c in rows]),
            step=step, vtype=vtype, tb=tb,
        )

    def slice(self, start: int, stop: int) -> "Bars":
        s = slice(start, stop)
        return Bars(self.t[s], self.o[s], self.h[s], self.l[s], self.c[s], self.v[s], self.step, self.vtype,
                    None if self.tb is None else self.tb[s])

    def upto(self, n: int) -> "Bars":
        """First n bars (information available at the close of bar n-1)."""
        return self.slice(0, n)

    @classmethod
    def from_arrays(cls, o, h, l, c, v=None, t0: int = 1_700_000_000, step: int = 3600) -> "Bars":  # noqa: E741
        n = len(c)
        return cls(
            t=t0 + np.arange(n, dtype=np.int64) * step,
            o=np.asarray(o, float), h=np.asarray(h, float), l=np.asarray(l, float), c=np.asarray(c, float),
            v=np.full(n, np.nan) if v is None else np.asarray(v, float), step=step,
        )
