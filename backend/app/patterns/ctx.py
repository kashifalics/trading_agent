"""What every family detector receives for one chunk of candles (all arrays chunk-local, same length, oldest first).

Detectors must be causal: an occurrence reported at index i may use candles 0..i only, swings only once confirmed
(Swing.confirm_idx <= i), and levels exactly as given (they are already point-in-time).
"""
from dataclasses import dataclass, field

import numpy as np

from app.market_structure.swings import Swing
from app.patterns.context import Levels


@dataclass
class ChunkCtx:
    t: np.ndarray  # candle open, epoch seconds
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray  # noqa: E741
    c: np.ndarray
    v: np.ndarray
    atr: np.ndarray
    step: int  # nominal seconds per candle
    swings: list[Swing]  # standard sensitivity (3 left / 3 right), as used by the platform's structure detectors
    swings_int: list[Swing]  # internal structure (2 / 2)
    swings_ext: list[Swing]  # external structure (5 / 5)
    levels: Levels | None = None
    trend: np.ndarray | None = None  # structure trend (-1/0/1) known at each close
    events: dict = field(default_factory=dict)  # outputs of the platform's existing detectors, by kind, for combinations

    @property
    def n(self) -> int:
        return len(self.c)


def swing_arrays(swings: list[Swing], kind: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(idx, price, confirm_idx) of swings of one kind, ordered by confirmation."""
    s = [x for x in swings if x.kind == kind]
    return (np.array([x.idx for x in s], dtype=np.int64), np.array([x.price for x in s], dtype=float),
            np.array([x.confirm_idx for x in s], dtype=np.int64))
