"""The user's `detect_flexible_double_top` (pasted 2026-11-12), vectorised with identical results, plus its mirror image.

Rules for the candle at position i (only candles before i and the close of i are used, so the signal is known at i's close):
  window  = the `lookback` candles before i
  peak 1  = the window's highest high (first one if tied); at least 5 window candles from peak 1 to the end of the window
  trough  = the lowest low from peak 1 on (first if tied)
  peak 2  = the highest high from the trough on (first if tied); it must come after the trough
  signal  = |peak 1 - peak 2| <= peak 1 x tolerance and candle i closes below the trough (the neckline)
Double bottom: the same rules on the price mirrored (lows for highs), the signal is a close above the neckline high.
One signal per pattern instance (pair of peaks): the first close through the neckline.
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

LOOKBACK = 20
TOLERANCE = 0.0005
MIN_TAIL = 5  # `if len(remaining_window) < 5: continue`
CHUNK = 200_000


def _tops(h: np.ndarray, lo: np.ndarray, c: np.ndarray, lookback: int, tol: float):
    """(signal index, peak-1 index, peak-2 index, structural level) for double tops on (h, l, c); tolerance is relative to |peak 1|."""
    n = len(h)
    if n <= lookback:
        z = np.array([], dtype=np.int64)
        return z, z, z, np.array([], dtype=float)
    Wh = sliding_window_view(h, lookback)[: n - lookback]  # row r covers candles [r, r + lookback) and judges candle i = r + lookback
    Wl = sliding_window_view(lo, lookback)[: n - lookback]
    col = np.arange(lookback)
    out = []
    for s in range(0, len(Wh), CHUNK):
        wh, wl = Wh[s:s + CHUNK], Wl[s:s + CHUNK]
        rows = np.arange(len(wh))
        p1 = wh.argmax(1)
        p1v = wh[rows, p1]
        tail_ok = lookback - p1 >= MIN_TAIL
        tr = np.where(col[None, :] >= p1[:, None], wl, np.inf).argmin(1)
        tv = wl[rows, tr]
        p2 = np.where(col[None, :] >= tr[:, None], wh, -np.inf).argmax(1)
        p2v = wh[rows, p2]
        i = rows + s + lookback
        ok = tail_ok & (np.abs(p1v - p2v) <= np.abs(p1v) * tol) & (p2 > tr) & (c[i] < tv)
        k = np.flatnonzero(ok)
        base = i[k] - lookback
        out.append((i[k], base + p1[k], base + p2[k], np.maximum(p1v[k], p2v[k])))
    i, a, b, lv = (np.concatenate(x) for x in zip(*out))
    return i.astype(np.int64), a.astype(np.int64), b.astype(np.int64), lv


def detect(h: np.ndarray, lo: np.ndarray, c: np.ndarray, side: int, lookback: int = LOOKBACK, tol: float = TOLERANCE,
           dedupe: bool = True) -> dict:
    """side -1: double top (sell); side +1: double bottom (buy). Returns idx (signal candle), peak1, peak2 and level (the higher peak
    of a top / the lower bottom of a bottom: the structural invalidation price before any buffer)."""
    h, lo, c = (np.asarray(x, dtype=float) for x in (h, lo, c))
    if side < 0:
        i, p1, p2, lv = _tops(h, lo, c, lookback, tol)
    else:  # mirror: lows become highs; |peak 1| keeps the tolerance positive
        i, p1, p2, lv = _tops(-lo, -h, -c, lookback, tol)
        lv = -lv
    if dedupe and len(i):
        _, first = np.unique(p1 * (len(h) + 1) + p2, return_index=True)
        keep = np.sort(first)
        i, p1, p2, lv = i[keep], p1[keep], p2[keep], lv[keep]
    return {"idx": i, "peak1": p1, "peak2": p2, "level": lv}
