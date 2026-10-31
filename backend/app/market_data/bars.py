"""Float64 columnar view of candles for analysis code (storage stays Decimal)."""
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

    def __len__(self) -> int:
        return len(self.t)

    @classmethod
    def from_candles(cls, candles: list[Candle], step: int, include_incomplete: bool = False) -> "Bars":
        rows = [c for c in candles if include_incomplete or c.complete]
        rows.sort(key=lambda c: c.ts)
        return cls(
            t=np.array([int(c.ts.timestamp()) for c in rows], dtype=np.int64),
            o=np.array([float(c.open) for c in rows]),
            h=np.array([float(c.high) for c in rows]),
            l=np.array([float(c.low) for c in rows]),
            c=np.array([float(c.close) for c in rows]),
            v=np.array([float(c.volume) if c.volume is not None else np.nan for c in rows]),
            step=step,
        )

    def slice(self, start: int, stop: int) -> "Bars":
        s = slice(start, stop)
        return Bars(self.t[s], self.o[s], self.h[s], self.l[s], self.c[s], self.v[s], self.step)

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
